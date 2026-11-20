"""Starting the saved VM must never create another instance."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from deploy import start_oci_vm


class FakeCompute:
    def __init__(self, state: str) -> None:
        self.state = state
        self.actions: list[tuple[str, str]] = []

    def get_instance(self, instance_id: str):
        return SimpleNamespace(data=SimpleNamespace(lifecycle_state=self.state))

    def instance_action(self, instance_id: str, action: str) -> None:
        self.actions.append((instance_id, action))


class StartExistingVmTest(unittest.TestCase):
    def test_running_vm_is_reused_without_action(self) -> None:
        compute = FakeCompute("RUNNING")
        with patch.object(start_oci_vm.oci, "wait_until") as wait:
            start_oci_vm.ensure_running(compute, "saved-vm", start=True)
        self.assertEqual(compute.actions, [])
        wait.assert_not_called()

    def test_stopped_vm_is_started_once(self) -> None:
        compute = FakeCompute("STOPPED")
        with patch.object(start_oci_vm.oci, "wait_until") as wait:
            start_oci_vm.ensure_running(compute, "saved-vm", start=True)
        self.assertEqual(compute.actions, [("saved-vm", "START")])
        wait.assert_called_once()

    def test_read_only_mode_does_not_start_stopped_vm(self) -> None:
        compute = FakeCompute("STOPPED")
        with self.assertRaisesRegex(RuntimeError, "STOPPED"):
            start_oci_vm.ensure_running(compute, "saved-vm", start=False)
        self.assertEqual(compute.actions, [])


if __name__ == "__main__":
    unittest.main()
