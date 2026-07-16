"""
Ledger ORM models.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from sqlalchemy import ForeignKey
from sqlalchemy import Numeric
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from services.database import (
    Base,
    TimestampMixin,
    UUIDMixin,
)


class JournalModel(
    UUIDMixin,
    TimestampMixin,
    Base,
):
    __tablename__ = "journals"

    reference: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
        index=True,
    )

    entries: Mapped[list["LedgerEntryModel"]] = relationship(
        back_populates="journal",
        cascade="all, delete-orphan",
    )


class LedgerEntryModel(
    UUIDMixin,
    TimestampMixin,
    Base,
):
    __tablename__ = "ledger_entries"

    journal_id: Mapped[str] = mapped_column(
        ForeignKey("journals.id"),
        nullable=False,
        index=True,
    )

    account_code: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    side: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(20, 8),
        nullable=False,
    )

    journal: Mapped[JournalModel] = relationship(
        back_populates="entries"
    )