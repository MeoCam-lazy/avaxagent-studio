"""Declarative base + shared column mixins."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, MetaData, Numeric, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

# Deterministic constraint names so Alembic autogenerate diffs are stable.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class _TokenAmount(TypeDecorator[int]):
    """uint256 token amounts (atomic units), stored as NUMERIC(78, 0).

    The driver returns ``Decimal`` for NUMERIC; this loads exact ``int`` so
    the ``Mapped[int]`` annotations hold. web3 rejects ``Decimal`` for
    ``uint256``, and float (``asdecimal=False``) would lose precision.
    """

    impl = Numeric(78, 0)
    cache_ok = True

    def process_result_value(self, value: Decimal | None, dialect: Any) -> int | None:
        return None if value is None else int(value)


TokenAmount = _TokenAmount()


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class UUIDPrimaryKey:
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)


class Timestamps:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
