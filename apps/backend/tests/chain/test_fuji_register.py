from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.fuji


@pytest.mark.skipif(
    os.getenv("FUJI_E2E") != "1",
    reason="Only run when FUJI_E2E=1 is set",
)
def test_fuji_register():
    # Placeholder for live Fuji integration test
    pass
