"""unique constraint on (chain_id, chain_job_id) for ERC-8183 escrow jobs

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-11

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_jobs_chain_job_id",
        "jobs",
        ["chain_id", "chain_job_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_jobs_chain_job_id", "jobs", type_="unique")
