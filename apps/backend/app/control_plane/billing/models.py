from __future__ import annotations

import uuid
from enum import Enum

from sqlalchemy import BigInteger, ForeignKey, String, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.model_base import Base, Timestamps, TokenAmount, UUIDPrimaryKey


class LedgerKind(str, Enum):
    INCOME = "income"  # client payment received (x402 transfer or ERC-8183 settle)
    STUDIO_FEE = "studio_fee"  # studio cut, settings.studio_fee_bps
    PAYOUT = "payout"  # withdrawal to the owner
    GAS = "gas"  # AVAX spent by the agent wallet (informational)


class PayoutStatus(str, Enum):
    REQUESTED = "requested"
    SUBMITTED = "submitted"
    CONFIRMED = "confirmed"
    FAILED = "failed"


class LedgerEntry(UUIDPrimaryKey, Timestamps, Base):
    """Append-only, double-entry-friendly record of value movements."""

    __tablename__ = "ledger_entries"

    agent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agents.id"), index=True)
    job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("jobs.id"), nullable=True)
    kind: Mapped[LedgerKind] = mapped_column(SAEnum(LedgerKind, native_enum=False))
    asset: Mapped[str] = mapped_column(String(42))  # token address, or "AVAX"
    amount_atomic: Mapped[int] = mapped_column(TokenAmount)
    chain_id: Mapped[int] = mapped_column(BigInteger)
    tx_hash: Mapped[str | None] = mapped_column(String(66), nullable=True)
    log_index: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # Set on PAYOUT rows only: the withdrawal this row books, so a failed
    # payout can drop its row and a confirmed one can stamp the tx hash.
    payout_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("payouts.id"), nullable=True, unique=True
    )
    # Set on STUDIO_FEE rows once a sweep claims them. ``tx_hash`` keeps
    # pointing at the payment the fee came from.
    fee_sweep_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("fee_sweeps.id"), nullable=True, index=True
    )

    __table_args__ = (
        UniqueConstraint("chain_id", "tx_hash", "log_index", "kind", name="uq_ledger_onchain"),
    )


class Payout(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "payouts"

    agent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agents.id"), index=True)
    owner_id: Mapped[str] = mapped_column(String(128), index=True)
    destination: Mapped[str] = mapped_column(String(42))
    asset: Mapped[str] = mapped_column(String(42))
    amount_atomic: Mapped[int] = mapped_column(TokenAmount)
    status: Mapped[PayoutStatus] = mapped_column(
        SAEnum(PayoutStatus, native_enum=False), default=PayoutStatus.REQUESTED
    )
    tx_hash: Mapped[str | None] = mapped_column(String(66), nullable=True)


class FeeSweep(UUIDPrimaryKey, Timestamps, Base):
    """One transfer of accumulated studio fees from an agent wallet to the treasury.

    Same lifecycle as ``Payout`` (``submitted`` -> ``confirmed`` / ``failed``),
    minus ``requested``: the sweeper creates it already claimed.
    """

    __tablename__ = "fee_sweeps"

    agent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agents.id"), index=True)
    destination: Mapped[str] = mapped_column(String(42))
    asset: Mapped[str] = mapped_column(String(42))
    amount_atomic: Mapped[int] = mapped_column(TokenAmount)
    status: Mapped[PayoutStatus] = mapped_column(
        SAEnum(PayoutStatus, native_enum=False), default=PayoutStatus.SUBMITTED
    )
    tx_hash: Mapped[str | None] = mapped_column(String(66), nullable=True)
