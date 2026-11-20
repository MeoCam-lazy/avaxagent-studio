"""A repeated relayer setup must reuse the same Turnkey wallet."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from deploy import create_turnkey_relayer as helper


class CreateTurnkeyRelayerTest(unittest.TestCase):
    def test_creates_once_and_reuses_saved_public_identifiers(self) -> None:
        created: list[str] = []

        class FakeAdmin:
            def __init__(self, **_kwargs: str) -> None:
                pass

            async def create_agent_sub_org(self, name: str):
                created.append(name)
                return type(
                    "Wallet",
                    (),
                    {
                        "sub_org_id": "child-org",
                        "wallet_id": "wallet-id",
                        "address": "0x" + "12" * 20,
                    },
                )()

        env = {
            "TURNKEY_ORGANIZATION_ID": "parent-org",
            "TURNKEY_API_PUBLIC_KEY": "public-key",
            "TURNKEY_API_PRIVATE_KEY": "test-private-key",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = Path(temp_dir) / "relayer.json"
            with (
                patch.object(helper, "STATE_PATH", state_path),
                patch.object(helper, "HttpTurnkeyAdmin", FakeAdmin),
                patch.object(helper, "dotenv_values", return_value=env),
                redirect_stdout(io.StringIO()),
            ):
                helper.main()
                helper.main()

            self.assertEqual(created, ["Studio Fuji x402 Relayer"])
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["organization_id"], "child-org")
            self.assertEqual(state["address"], "0x" + "12" * 20)
            self.assertNotIn("test-private-key", state_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
