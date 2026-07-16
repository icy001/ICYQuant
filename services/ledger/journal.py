"""
Journal aggregate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID, uuid4

from .model import LedgerEntry
from .enums import EntrySide


@dataclass
class Journal:
    journal_id: UUID = field(
        default_factory=uuid4
    )

    entries: list[LedgerEntry] = field(
        default_factory=list
    )

    def add_entry(
        self,
        account_code: str,
        side: EntrySide,
        amount: Decimal,
    ) -> None:
        self.entries.append(
            LedgerEntry(
                journal_id=self.journal_id,
                account_code=account_code,
                side=side,
                amount=amount,
            )
        )

    @property
    def debit_total(self) -> Decimal:
        return sum(
            e.amount
            for e in self.entries
            if e.side == EntrySide.DEBIT
        )

    @property
    def credit_total(self) -> Decimal:
        return sum(
            e.amount
            for e in self.entries
            if e.side == EntrySide.CREDIT
        )

    def is_balanced(self) -> bool:
        return (
            self.debit_total
            ==
            self.credit_total
        )