"""Commit 015 §8 — SQLAlchemy models for the account System of Record.

Reuses the project's existing declarative base and mixins rather than
introducing a second DB stack (§8)::

    account                      one row per broker account
       │
       ├── account_balance_snapshot     one row per sync (balance)
       └── position_snapshot            one row per sync (header)
               └── position_snapshot_item    one row per position

Migrated by ``alembic/versions/003_create_account_position_snapshots.py``.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from services.database import Base, TimestampMixin, UUIDMixin

_MONEY = Numeric(20, 4)
_QUANTITY = Numeric(20, 6)
_RATE = Numeric(12, 6)


class AccountModel(Base, UUIDMixin, TimestampMixin):
    """Account registry (§8 ``account``)."""

    __tablename__ = "account"

    account_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128), default="")
    broker: Mapped[str] = mapped_column(String(64), default="")
    currency: Mapped[str] = mapped_column(String(8), default="CNY")
    status: Mapped[str] = mapped_column(String(16), default="OFFLINE")

    balances: Mapped[list["AccountBalanceSnapshotModel"]] = relationship(
        back_populates="account", cascade="all, delete-orphan", lazy="selectin"
    )
    snapshots: Mapped[list["PositionSnapshotModel"]] = relationship(
        back_populates="account", cascade="all, delete-orphan", lazy="selectin"
    )


class AccountBalanceSnapshotModel(Base, UUIDMixin, TimestampMixin):
    """One balance observation per sync (§8 / §7 — never overwritten)."""

    __tablename__ = "account_balance_snapshot"
    __table_args__ = (
        UniqueConstraint("snapshot_id", name="uq_account_balance_snapshot_id"),
        Index(
            "ix_account_balance_snapshot_account_time",
            "account_id",
            "broker_timestamp",
        ),
    )

    snapshot_id: Mapped[str] = mapped_column(String(96), index=True)
    account_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("account.account_id"), index=True
    )
    currency: Mapped[str] = mapped_column(String(8), default="CNY")

    cash: Mapped[Decimal] = mapped_column(_MONEY, default=0)
    available_cash: Mapped[Decimal] = mapped_column(_MONEY, default=0)
    frozen_cash: Mapped[Decimal] = mapped_column(_MONEY, default=0)
    market_value: Mapped[Decimal] = mapped_column(_MONEY, default=0)
    total_asset: Mapped[Decimal] = mapped_column(_MONEY, default=0)
    buying_power: Mapped[Decimal] = mapped_column(_MONEY, default=0)

    broker_timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    received_timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sync_latency_ms: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(14, 3), nullable=True
    )
    source: Mapped[str] = mapped_column(String(16), default="BROKER")
    sequence: Mapped[int] = mapped_column(Integer, default=0)

    account: Mapped[AccountModel] = relationship(back_populates="balances")


class PositionSnapshotModel(Base, UUIDMixin, TimestampMixin):
    """One position-set observation per sync (§8 header)."""

    __tablename__ = "position_snapshot"
    __table_args__ = (
        UniqueConstraint("snapshot_id", name="uq_position_snapshot_id"),
        Index(
            "ix_position_snapshot_account_time",
            "account_id",
            "broker_timestamp",
        ),
    )

    snapshot_id: Mapped[str] = mapped_column(String(96), index=True)
    account_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("account.account_id"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, default=0)
    position_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="SYNCED")
    source: Mapped[str] = mapped_column(String(16), default="BROKER")

    broker_timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    received_timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sync_latency_ms: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(14, 3), nullable=True
    )
    reconciliation_status: Mapped[Optional[str]] = mapped_column(
        String(24), nullable=True
    )
    reconciliation_outcome: Mapped[Optional[str]] = mapped_column(
        String(8), nullable=True
    )

    account: Mapped[AccountModel] = relationship(back_populates="snapshots")
    items: Mapped[list["PositionSnapshotItemModel"]] = relationship(
        back_populates="snapshot", cascade="all, delete-orphan", lazy="selectin"
    )


class PositionSnapshotItemModel(Base, UUIDMixin, TimestampMixin):
    """One position within a snapshot (§8 ``position_snapshot_item``)."""

    __tablename__ = "position_snapshot_item"
    __table_args__ = (
        Index("ix_position_snapshot_item_account_symbol", "account_id", "symbol"),
    )

    snapshot_id: Mapped[str] = mapped_column(
        String(96), ForeignKey("position_snapshot.snapshot_id"), index=True
    )
    account_id: Mapped[str] = mapped_column(String(64), index=True)

    symbol: Mapped[str] = mapped_column(String(32), index=True)
    exchange: Mapped[str] = mapped_column(String(8), default="")

    quantity: Mapped[Decimal] = mapped_column(_QUANTITY, default=0)
    available_quantity: Mapped[Decimal] = mapped_column(_QUANTITY, default=0)
    frozen_quantity: Mapped[Decimal] = mapped_column(_QUANTITY, default=0)

    average_cost: Mapped[Decimal] = mapped_column(_MONEY, default=0)
    market_price: Mapped[Optional[Decimal]] = mapped_column(_MONEY, nullable=True)
    market_value: Mapped[Optional[Decimal]] = mapped_column(_MONEY, nullable=True)
    unrealized_pnl: Mapped[Optional[Decimal]] = mapped_column(_MONEY, nullable=True)
    unrealized_pnl_pct: Mapped[Optional[Decimal]] = mapped_column(
        _RATE, nullable=True
    )

    status: Mapped[str] = mapped_column(String(16), default="VALID")
    broker_timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    received_timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    snapshot: Mapped[PositionSnapshotModel] = relationship(back_populates="items")


__all__ = [
    "AccountModel",
    "AccountBalanceSnapshotModel",
    "PositionSnapshotModel",
    "PositionSnapshotItemModel",
]
