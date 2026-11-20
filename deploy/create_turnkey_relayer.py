"""Create one dedicated Fuji relayer wallet in a Turnkey sub-organization.

Run with apps/backend/.venv/Scripts/python.exe deploy/create_turnkey_relayer.py.
The state file contains public identifiers only and prevents duplicate creation
when this command is run again. Fund the printed address with Fuji AVAX before
using it for x402 settlement.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import dotenv_values
from web3 import Web3

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "deploy/turnkey-relayer-state.json"
sys.path.insert(0, str(ROOT / "apps/backend"))

from app.control_plane.wallets.turnkey_admin import HttpTurnkeyAdmin  # noqa: E402


def required(values: dict, key: str) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Missing {key} in apps/backend/.env")
    return value.strip()


def main() -> None:
    env = dotenv_values(ROOT / "apps/backend/.env")
    parent_org = required(env, "TURNKEY_ORGANIZATION_ID")

    if STATE_PATH.exists():
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        if state.get("parent_organization_id") != parent_org:
            raise ValueError("Relayer state belongs to a different Turnkey parent organization")
        organization_id = required(state, "organization_id")
        address = Web3.to_checksum_address(state["address"])
        print("Existing relayer sub-organization reused; no wallet was created.")
        print(f"RELAYER_ORGANIZATION_ID={organization_id}")
        print(f"RELAYER_SIGN_WITH={address}")
        return

    admin = HttpTurnkeyAdmin(
        base_url=env.get("TURNKEY_API_BASE_URL") or "https://api.turnkey.com",
        api_public_key=required(env, "TURNKEY_API_PUBLIC_KEY"),
        api_private_key=required(env, "TURNKEY_API_PRIVATE_KEY"),
        organization_id=parent_org,
    )
    wallet = asyncio.run(admin.create_agent_sub_org("Studio Fuji x402 Relayer"))
    if not wallet.sub_org_id or not wallet.wallet_id or not Web3.is_address(wallet.address):
        raise RuntimeError("Turnkey returned an incomplete relayer wallet")

    state = {
        "parent_organization_id": parent_org,
        "organization_id": wallet.sub_org_id,
        "wallet_id": wallet.wallet_id,
        "address": Web3.to_checksum_address(wallet.address),
    }
    fd = os.open(STATE_PATH, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as output:
        json.dump(state, output, indent=2)
        output.write("\n")
    print("Dedicated Fuji relayer created. Fund this address with Fuji AVAX:")
    print(f"RELAYER_ORGANIZATION_ID={state['organization_id']}")
    print(f"RELAYER_SIGN_WITH={state['address']}")


if __name__ == "__main__":
    main()
