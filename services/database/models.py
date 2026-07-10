"""
SQLAlchemy database models.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
)

from sqlalchemy import (
    Text,
    DateTime,
)


class Base(
    DeclarativeBase
):
    pass


class LedgerEventModel(
    Base
):
    __tablename__ = (
        "ledger_events"
    )

    id: Mapped[str] = mapped_column(
        primary_key=True
    )

    event_type: Mapped[str] = mapped_column(
        Text
    )

    payload: Mapped[str] = mapped_column(
        Text
    )

    created_at: Mapped[datetime] = (
        mapped_column(
            DateTime
        )
    )


class AuditRecordModel(
    Base
):
    __tablename__ = (
        "audit_records"
    )

    id: Mapped[str] = mapped_column(
        primary_key=True
    )

    action: Mapped[str] = mapped_column(
        Text
    )

    reason: Mapped[str] = mapped_column(
        Text
    )

    created_at: Mapped[datetime] = (
        mapped_column(
            DateTime
        )
    )