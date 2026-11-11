"""ledger_entries.payout_id links a PAYOUT row to its withdrawal

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-11

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("ledger_entries", sa.Column("payout_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_ledger_entries_payout_id_payouts"),
        "ledger_entries",
        "payouts",
        ["payout_id"],
        ["id"],
    )
    op.create_unique_constraint(
        op.f("uq_ledger_entries_payout_id"), "ledger_entries", ["payout_id"]
    )


def downgrade() -> None:
    op.drop_constraint(op.f("uq_ledger_entries_payout_id"), "ledger_entries", type_="unique")
    op.drop_constraint(
        op.f("fk_ledger_entries_payout_id_payouts"), "ledger_entries", type_="foreignkey"
    )
    op.drop_column("ledger_entries", "payout_id")
