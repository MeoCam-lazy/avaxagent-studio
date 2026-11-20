"""Copy local Turnkey/LLM settings to an existing OCI VM for Fuji testing.

Run with apps/backend/.venv/Scripts/python.exe deploy/configure_oci_fuji.py.
Secrets travel through SSH stdin and are never printed or stored in the repo.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import httpx
from dotenv import dotenv_values
from web3 import Web3


ROOT = Path(__file__).resolve().parents[1]
RPC_URL = "https://api.avax-test.network/ext/bc/C/rpc"


def required(values: dict, key: str) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Missing {key}")
    if "\n" in value or "\r" in value:
        raise ValueError(f"Invalid newline in {key}")
    return value


def rpc(method: str) -> str:
    response = httpx.post(
        RPC_URL,
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": []},
        timeout=20,
    )
    response.raise_for_status()
    result = response.json()
    if "error" in result or "result" not in result:
        raise RuntimeError(f"Fuji RPC failed: {method}")
    return result["result"]


def main() -> None:
    backend = dotenv_values(ROOT / "apps/backend/.env")
    oci = dotenv_values(ROOT / "deploy/oci.env")
    state = json.loads((ROOT / "deploy/oci-state.json").read_text(encoding="utf-8"))

    org = required(backend, "TURNKEY_ORGANIZATION_ID")
    settings = {
        "NETWORK": "avalanche-fuji",
        "RPC_URL": RPC_URL,
        "TURNKEY_ORGANIZATION_ID": org,
        "TURNKEY_API_PUBLIC_KEY": required(backend, "TURNKEY_API_PUBLIC_KEY"),
        "TURNKEY_API_PRIVATE_KEY": required(backend, "TURNKEY_API_PRIVATE_KEY"),
        "LLM_PROVIDER": required(backend, "LLM_PROVIDER"),
        "LLM_MODEL": required(backend, "LLM_MODEL"),
        "LLM_API_KEY": required(backend, "LLM_API_KEY"),
    }
    relayer_state_path = ROOT / "deploy/turnkey-relayer-state.json"
    if relayer_state_path.exists():
        relayer = json.loads(relayer_state_path.read_text(encoding="utf-8"))
        if relayer.get("parent_organization_id") != org:
            raise ValueError("Relayer state belongs to a different Turnkey parent organization")
        settings["RELAYER_ORGANIZATION_ID"] = required(relayer, "organization_id")
        settings["RELAYER_SIGN_WITH"] = Web3.to_checksum_address(required(relayer, "address"))
    # When no dedicated state exists, leave the VM's current RELAYER_* settings alone.
    if int(rpc("eth_chainId"), 16) != 43113:
        raise RuntimeError("RPC is not Avalanche Fuji")
    settings["INDEXER_START_BLOCK"] = str(int(rpc("eth_blockNumber"), 16))

    remote_program = '''
import json, os
from pathlib import Path

settings = json.loads(PAYLOAD)
path = Path("/home/ubuntu/avaxagent-studio/apps/backend/.env")
if not path.is_file():
    raise SystemExit("Remote backend .env does not exist")
os.umask(0o077)
old = path.read_text(encoding="utf-8").splitlines()
existing_start = next(
    (line.split("=", 1)[1].strip() for line in old if line.startswith("INDEXER_START_BLOCK=")),
    "",
)
if existing_start:
    settings.pop("INDEXER_START_BLOCK")
lines = [line for line in old if line.split("=", 1)[0] not in settings]
lines.extend(f"{key}={value}" for key, value in settings.items())
temp = path.with_suffix(".env.tmp")
temp.write_text("\\n".join(lines) + "\\n", encoding="utf-8")
os.chmod(temp, 0o600)
os.replace(temp, path)
print(f"Remote Fuji settings updated; indexer start block: {existing_start or settings['INDEXER_START_BLOCK']}; secrets hidden")
'''.replace("PAYLOAD", repr(json.dumps(settings)))

    ssh_key = required(oci, "OCI_SSH_PRIVATE_KEY_PATH")
    ip = state["public_ip"]
    command = [
        "ssh", "-i", ssh_key, "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new",
        f"ubuntu@{ip}", "python3 -",
    ]
    done = subprocess.run(command, input=remote_program, text=True, capture_output=True)
    if done.returncode:
        print(done.stderr.strip() or "SSH configuration failed", file=sys.stderr)
        raise SystemExit(done.returncode)
    print(done.stdout.strip())
    if relayer_state_path.exists():
        print(f"Relayer: {settings['RELAYER_SIGN_WITH']}")
    else:
        print("Relayer settings on VM preserved (no local dedicated state)")


if __name__ == "__main__":
    main()
