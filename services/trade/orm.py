"""
Trade ORM model.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from sqlalchemy import Numeric
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from services.database import (
    Base,
    TimestampMixin,
    UUIDMixin,
)


class TradeModel(
    UUIDMixin,
    TimestampMixin,
    Base,
):
    __tablename__ = "trades"

    order_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
    )

    account_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    execution_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        unique=True,
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
    )

    price: Mapped[Decimal] = mapped_column(
        Numeric(20, 8),
        nullable=False,
    )

    commission: Mapped[Decimal] = mapped_column(
        Numeric(20, 8),
        nullable=False,
        default=Decimal("0"),
    )

    liquidity: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="UNKNOWN",
    )