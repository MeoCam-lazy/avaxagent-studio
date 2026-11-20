"""Provision the network and Ubuntu VM for Avaxagent Studio with the OCI SDK.

Run `python deploy/provision_oci.py` to check the configuration and OCI access.
Run `python deploy/provision_oci.py --apply` to create or resume resources.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import subprocess
from pathlib import Path
from urllib.request import urlopen

import oci

HERE = Path(__file__).resolve().parent
CONFIG_PATH = HERE / "oci.env"
STATE_PATH = HERE / "oci-state.json"
NAME = "avaxagent-studio"


def read_env() -> dict[str, str]:
    if not CONFIG_PATH.is_file():
        raise ValueError(f"Missing {CONFIG_PATH}")
    result: dict[str, str] = {}
    for raw in CONFIG_PATH.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"Invalid line in {CONFIG_PATH}: {line[:30]}")
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def required(env: dict[str, str], key: str) -> str:
    value = env.get(key, "")
    if not value or value.startswith("..."):
        raise ValueError(f"Fill {key} in {CONFIG_PATH}")
    return value


def key_path(env: dict[str, str], key: str) -> Path:
    path = Path(required(env, key)).expanduser()
    if not path.is_file():
        raise ValueError(f"{key} does not point to an existing file: {path}")
    return path


def ssh_cidr(env: dict[str, str]) -> str:
    value = env.get("OCI_SSH_SOURCE_CIDR", "")
    if not value or value.startswith("..."):
        with urlopen("https://api.ipify.org", timeout=15) as response:
            value = response.read().decode("ascii").strip() + "/32"
    network = ipaddress.ip_network(value, strict=False)
    if network.version != 4 or network.prefixlen < 24:
        raise ValueError("OCI_SSH_SOURCE_CIDR must be a narrow IPv4 CIDR (prefer /32)")
    return str(network)


def config_and_inputs() -> tuple[dict, dict]:
    env = read_env()
    vcn = ipaddress.ip_network(required(env, "OCI_VCN_CIDR"), strict=True)
    subnet = ipaddress.ip_network(required(env, "OCI_SUBNET_CIDR"), strict=True)
    if vcn.version != 4 or subnet.version != 4 or not subnet.subnet_of(vcn):
        raise ValueError("OCI_SUBNET_CIDR must be an IPv4 subnet inside OCI_VCN_CIDR")
    public_key = key_path(env, "OCI_SSH_PUBLIC_KEY_PATH").read_text(encoding="utf-8").strip()
    if not public_key.startswith(("ssh-ed25519 ", "ssh-rsa ", "ecdsa-sha2-")):
        raise ValueError("OCI_SSH_PUBLIC_KEY_PATH must contain an OpenSSH public key")
    private_key_path = key_path(env, "OCI_SSH_PRIVATE_KEY_PATH")
    check = subprocess.run(
        ["ssh-keygen", "-y", "-P", "", "-f", str(private_key_path)],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if check.returncode or check.stdout.split()[:2] != public_key.split()[:2]:
        raise ValueError("OCI SSH public/private key files do not match or need a passphrase")
    api_key_path = key_path(env, "OCI_PRIVATE_KEY_PATH")
    config = {
        "user": required(env, "OCI_USER_OCID"),
        "tenancy": required(env, "OCI_TENANCY_OCID"),
        "fingerprint": required(env, "OCI_FINGERPRINT"),
        "key_file": str(api_key_path),
        "region": required(env, "OCI_REGION"),
    }
    oci.config.validate_config(config)
    inputs = {
        "compartment_id": env.get("OCI_COMPARTMENT_OCID") or config["tenancy"],
        "vcn_cidr": str(vcn),
        "subnet_cidr": str(subnet),
        "ssh_cidr": ssh_cidr(env),
        "public_key": public_key,
        "shape": required(env, "OCI_SHAPE"),
        "ocpus": float(required(env, "OCI_OCPUS")),
        "memory_gb": float(required(env, "OCI_MEMORY_GB")),
    }
    return config, inputs


def save_state(state: dict) -> None:
    temp = STATE_PATH.with_suffix(".tmp")
    temp.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    temp.replace(STATE_PATH)


def get_or_create(state: dict, key: str, get, create, label: str):
    if key in state:
        item = get(state[key]).data
        print(f"Using existing {label}: {item.id}")
        return item
    item = create().data
    state[key] = item.id
    save_state(state)
    print(f"Created {label}: {item.id}")
    return item


def image_for_shape(compute, compartment_id: str, shape: str):
    images = oci.pagination.list_call_get_all_results(
        compute.list_images, compartment_id, shape=shape
    ).data
    arch = "aarch64-" if "A1" in shape or "A2" in shape else ""
    prefix = f"Canonical-Ubuntu-24.04-{arch}"
    matches = [image for image in images if image.display_name.startswith(prefix)]
    if not matches:
        raise ValueError(f"No Ubuntu 24.04 image compatible with {shape} in this region")
    return max(matches, key=lambda image: image.time_created)


def preflight(config: dict, inputs: dict):
    identity = oci.identity.IdentityClient(config)
    network = oci.core.VirtualNetworkClient(config)
    compute = oci.core.ComputeClient(config)
    tenancy = identity.get_tenancy(config["tenancy"]).data
    subscriptions = identity.list_region_subscriptions(config["tenancy"]).data
    selected = next((item for item in subscriptions if item.region_name == config["region"]), None)
    if selected is None:
        raise ValueError(f"Tenancy is not subscribed to region {config['region']}")
    if not selected.is_home_region:
        raise ValueError("Selected region is not the tenancy home region required for Always Free")
    domains = identity.list_availability_domains(inputs["compartment_id"]).data
    if not domains:
        raise ValueError("No availability domain is visible in the target compartment")
    image = image_for_shape(compute, inputs["compartment_id"], inputs["shape"])
    print(f"OCI authentication: OK ({tenancy.name})")
    print(f"Region: {config['region']} (home region)")
    print(f"SSH source: {inputs['ssh_cidr']}")
    print(f"Ubuntu image: {image.display_name}")
    print(f"Availability domain: {domains[0].name}")
    return network, compute, domains[0].name, image


def provision(config: dict, inputs: dict, network, compute, domain: str, image) -> None:
    state = json.loads(STATE_PATH.read_text(encoding="utf-8")) if STATE_PATH.exists() else {}
    expected = {"region": config["region"], "compartment_id": inputs["compartment_id"]}
    for key, value in expected.items():
        if key in state and state[key] != value:
            raise ValueError(f"{STATE_PATH} belongs to a different {key}")
    if not state:
        existing = oci.pagination.list_call_get_all_results(
            network.list_vcns, inputs["compartment_id"]
        ).data
        if any(
            v.display_name == f"{NAME}-vcn" and v.lifecycle_state != "TERMINATED"
            for v in existing
        ):
            raise ValueError("A same-named VCN already exists; inspect OCI first")
        state.update(expected)
        save_state(state)

    models = oci.core.models
    compartment = inputs["compartment_id"]
    vcn = get_or_create(
        state,
        "vcn_id",
        network.get_vcn,
        lambda: network.create_vcn(
            models.CreateVcnDetails(
                compartment_id=compartment,
                cidr_block=inputs["vcn_cidr"],
                display_name=f"{NAME}-vcn",
                dns_label="avaxstudio",
            )
        ),
        "VCN",
    )
    oci.wait_until(network, network.get_vcn(vcn.id), "lifecycle_state", "AVAILABLE")

    gateway = get_or_create(
        state,
        "internet_gateway_id",
        network.get_internet_gateway,
        lambda: network.create_internet_gateway(
            models.CreateInternetGatewayDetails(
                compartment_id=compartment,
                vcn_id=vcn.id,
                is_enabled=True,
                display_name=f"{NAME}-internet",
            )
        ),
        "internet gateway",
    )
    oci.wait_until(
        network, network.get_internet_gateway(gateway.id), "lifecycle_state", "AVAILABLE"
    )

    route = get_or_create(
        state,
        "route_table_id",
        network.get_route_table,
        lambda: network.create_route_table(
            models.CreateRouteTableDetails(
                compartment_id=compartment,
                vcn_id=vcn.id,
                display_name=f"{NAME}-public-route",
                route_rules=[
                    models.RouteRule(
                        destination="0.0.0.0/0",
                        destination_type="CIDR_BLOCK",
                        network_entity_id=gateway.id,
                    )
                ],
            )
        ),
        "route table",
    )

    def tcp_rule(port: int, source: str):
        return models.IngressSecurityRule(
            protocol="6",
            source=source,
            source_type="CIDR_BLOCK",
            tcp_options=models.TcpOptions(
                destination_port_range=models.PortRange(min=port, max=port)
            ),
        )

    security = get_or_create(
        state,
        "security_list_id",
        network.get_security_list,
        lambda: network.create_security_list(
            models.CreateSecurityListDetails(
                compartment_id=compartment,
                vcn_id=vcn.id,
                display_name=f"{NAME}-public-security",
                ingress_security_rules=[
                    tcp_rule(22, inputs["ssh_cidr"]),
                    tcp_rule(80, "0.0.0.0/0"),
                    tcp_rule(443, "0.0.0.0/0"),
                    models.IngressSecurityRule(
                        protocol="1",
                        source="0.0.0.0/0",
                        source_type="CIDR_BLOCK",
                        icmp_options=models.IcmpOptions(type=3, code=4),
                    ),
                ],
                egress_security_rules=[
                    models.EgressSecurityRule(
                        protocol="all", destination="0.0.0.0/0", destination_type="CIDR_BLOCK"
                    )
                ],
            )
        ),
        "security list",
    )

    subnet = get_or_create(
        state,
        "subnet_id",
        network.get_subnet,
        lambda: network.create_subnet(
            models.CreateSubnetDetails(
                compartment_id=compartment,
                vcn_id=vcn.id,
                cidr_block=inputs["subnet_cidr"],
                display_name=f"{NAME}-public-subnet",
                dns_label="public",
                prohibit_public_ip_on_vnic=False,
                route_table_id=route.id,
                security_list_ids=[security.id],
            )
        ),
        "public subnet",
    )
    oci.wait_until(network, network.get_subnet(subnet.id), "lifecycle_state", "AVAILABLE")

    if "instance_id" not in state:
        existing_instances = oci.pagination.list_call_get_all_results(
            compute.list_instances, compartment
        ).data
        if any(
            item.display_name == f"{NAME}-vm" and item.lifecycle_state != "TERMINATED"
            for item in existing_instances
        ):
            raise ValueError("A same-named VM already exists; inspect OCI first")

    instance = get_or_create(
        state,
        "instance_id",
        compute.get_instance,
        lambda: compute.launch_instance(
            models.LaunchInstanceDetails(
                compartment_id=compartment,
                availability_domain=domain,
                display_name=f"{NAME}-vm",
                shape=inputs["shape"],
                shape_config=models.LaunchInstanceShapeConfigDetails(
                    ocpus=inputs["ocpus"], memory_in_gbs=inputs["memory_gb"]
                ),
                source_details=models.InstanceSourceViaImageDetails(image_id=image.id),
                create_vnic_details=models.CreateVnicDetails(
                    subnet_id=subnet.id, assign_public_ip=True
                ),
                metadata={"ssh_authorized_keys": inputs["public_key"]},
            )
        ),
        "Ubuntu VM",
    )
    oci.wait_until(compute, compute.get_instance(instance.id), "lifecycle_state", "RUNNING")
    attachments = compute.list_vnic_attachments(
        compartment_id=compartment, instance_id=instance.id
    ).data
    if not attachments:
        raise RuntimeError("VM is running, but its VNIC attachment is not visible yet")
    public_ip = network.get_vnic(attachments[0].vnic_id).data.public_ip
    if not public_ip:
        raise RuntimeError("VM is running, but no public IP was assigned")
    state["public_ip"] = public_ip
    save_state(state)
    print(f"VM is running at {public_ip}")
    print("Next: connect as ubuntu with OCI_SSH_PRIVATE_KEY_PATH, then install Docker and deploy.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Create or resume OCI resources")
    args = parser.parse_args()
    config, inputs = config_and_inputs()
    network, compute, domain, image = preflight(config, inputs)
    if args.apply:
        provision(config, inputs, network, compute, domain, image)
    else:
        print("Preflight succeeded. Run with --apply to create resources.")


if __name__ == "__main__":
    try:
        main()
    except oci.exceptions.ServiceError as exc:
        if exc.status == 500 and "Out of host capacity" in getattr(exc, "message", ""):
            raise SystemExit(
                "OCI has no capacity for the selected VM shape right now. "
                "Network resources are saved; rerun with --apply later."
            ) from None
        raise
