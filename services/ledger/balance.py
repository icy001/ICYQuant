"""
Ledger balance calculator.
"""

from __future__ import annotations

from decimal import Decimal

from .enums import EntrySide
from .journal import Journal
from .snapshot import LedgerSnapshot


class LedgerBalanceCalculator:
    def apply(
        self,
        snapshot: LedgerSnapshot,
        journal: Journal,
    ) -> None:
        for entry in journal.entries:
            amount = entry.amount

            if entry.side == EntrySide.CREDIT:
                amount = -amount

            snapshot.apply(
                entry.account_code,
                amount,
            )


class BalanceCalculator:
    def calculate(self, entries):
        balance = 0

        for entry in entries:
            if entry.direction == "CREDIT":
                balance += entry.amount
            else:
                balance -= entry.amount

        return balance