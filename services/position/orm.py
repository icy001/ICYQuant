"""
Position ORM model.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Numeric
from sqlalchemy import String
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from services.database import (
    Base,
    TimestampMixin,
    UUIDMixin,
)


class PositionModel(
    UUIDMixin,
    TimestampMixin,
    Base,
):
    __tablename__ = "positions"

    __table_args__ = (
        UniqueConstraint(
            "account_id",
            "symbol",
            name="uq_position_account_symbol",
        ),
    )

    account_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    symbol: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
    )

    quantity: Mapped[Decimal] = mapped_column(
        Numeric(20, 8),
        nullable=False,
        default=Decimal("0"),
    )

    average_cost: Mapped[Decimal] = mapped_column(
        Numeric(20, 8),
        nullable=False,
        default=Decimal("0"),
    )

    realized_pnl: Mapped[Decimal] = mapped_column(
        Numeric(20, 8),
        nullable=False,
        default=Decimal("0"),
    )

    version: Mapped[int] = mapped_column(
        nullable=False,
        default=1,
    )