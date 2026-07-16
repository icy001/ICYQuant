"""
Order ORM model.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from sqlalchemy import Enum
from sqlalchemy import Numeric
from sqlalchemy import String

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from services.database import (
    Base,
    TimestampMixin,
    UUIDMixin,
)

from .enums import (
    OrderSide,
    OrderStatus,
    OrderType,
    TimeInForce,
)


class OrderModel(
    UUIDMixin,
    TimestampMixin,
    Base,
):
    __tablename__ = "orders"

    symbol: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
    )

    side: Mapped[OrderSide] = mapped_column(
        Enum(OrderSide),
        nullable=False,
    )

    order_type: Mapped[OrderType] = mapped_column(
        Enum(OrderType),
        nullable=False,
    )

    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus),
        nullable=False,
        index=True,
    )

    time_in_force: Mapped[TimeInForce] = mapped_column(
        Enum(TimeInForce),
        nullable=False,
    )

    quantity: Mapped[Decimal] = mapped_column(
        Numeric(20, 8),
        nullable=False,
    )

    filled_quantity: Mapped[Decimal] = mapped_column(
        Numeric(20, 8),
        nullable=False,
        default=Decimal("0"),
    )

    average_price: Mapped[Decimal] = mapped_column(
        Numeric(20, 8),
        nullable=False,
        default=Decimal("0"),
    )

    limit_price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(20, 8),
        nullable=True,
    )

    stop_price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(20, 8),
        nullable=True,
    )

    version: Mapped[int] = mapped_column(
        nullable=False,
        default=1,
    )