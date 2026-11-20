"""Find or start the existing OCI VM recorded in oci-state.json.

Without --start this command is read-only. On success it prints only the
current public IPv4 address so shell scripts can use it for SSH.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import sys

import oci

if __package__:
    from .provision_oci import STATE_PATH, key_path, read_env, required, save_state
else:
    from provision_oci import STATE_PATH, key_path, read_env, required, save_state


def oci_config() -> dict[str, str]:
    env = read_env()
    config = {
        "user": required(env, "OCI_USER_OCID"),
        "tenancy": required(env, "OCI_TENANCY_OCID"),
        "fingerprint": required(env, "OCI_FINGERPRINT"),
        "key_file": str(key_path(env, "OCI_PRIVATE_KEY_PATH")),
        "region": required(env, "OCI_REGION"),
    }
    oci.config.validate_config(config)
    return config


def ensure_running(compute: object, instance_id: str, *, start: bool) -> None:
    instance = compute.get_instance(instance_id).data
    state = instance.lifecycle_state
    if state == "RUNNING":
        return
    if state == "STOPPING" and start:
        oci.wait_until(compute, compute.get_instance(instance_id), "lifecycle_state", "STOPPED")
        state = "STOPPED"
    if state == "STOPPED" and start:
        print("Starting existing OCI VM...", file=sys.stderr)
        compute.instance_action(instance_id, "START")
        state = "STARTING"
    if state == "STARTING" and start:
        oci.wait_until(compute, compute.get_instance(instance_id), "lifecycle_state", "RUNNING")
        return
    raise RuntimeError(f"Existing OCI VM is {state}; no VM was created")


def current_public_ip(compute: object, network: object, state: dict) -> str:
    attachments = compute.list_vnic_attachments(
        compartment_id=state["compartment_id"],
        instance_id=state["instance_id"],
    ).data
    for attachment in attachments:
        if attachment.lifecycle_state != "ATTACHED":
            continue
        public_ip = network.get_vnic(attachment.vnic_id).data.public_ip
        if public_ip:
            return str(ipaddress.IPv4Address(public_ip))
    raise RuntimeError("Running OCI VM has no attached VNIC with a public IPv4 address")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", action="store_true", help="Start the existing VM if stopped")
    args = parser.parse_args()

    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    if not state.get("instance_id") or not state.get("compartment_id"):
        raise ValueError(f"{STATE_PATH} has no existing instance_id or compartment_id")

    config = oci_config()
    if state.get("region") != config["region"]:
        raise ValueError("OCI region does not match the saved VM state")
    compute = oci.core.ComputeClient(config)
    network = oci.core.VirtualNetworkClient(config)
    ensure_running(compute, state["instance_id"], start=args.start)

    public_ip = current_public_ip(compute, network, state)
    if state.get("public_ip") != public_ip:
        print(f"Public IP changed to {public_ip}", file=sys.stderr)
        state["public_ip"] = public_ip
        save_state(state)
    print(public_ip)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, KeyError, oci.exceptions.ServiceError) as exc:
        raise SystemExit(str(exc)) from None
