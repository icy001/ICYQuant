"""
Ledger entry domain model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID, uuid4

from .enums import EntrySide


@dataclass
class LedgerEntry:
    journal_id: UUID
    account_code: str
    side: EntrySide
    amount: Decimal
    entry_id: UUID = field(default_factory=uuid4)