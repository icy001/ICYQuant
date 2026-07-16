"""
Ledger replay service.
"""

from __future__ import annotations

from .balance import (
    LedgerBalanceCalculator,
)
from .snapshot import (
    LedgerSnapshot,
)


class LedgerReplayService:
    def __init__(self):
        self.calculator = (
            LedgerBalanceCalculator()
        )

    def replay(
        self,
        journals,
    ) -> LedgerSnapshot:
        snapshot = LedgerSnapshot()

        for journal in journals:
            if not journal.is_balanced():
                raise ValueError(
                    "Unbalanced journal."
                )

            self.calculator.apply(
                snapshot,
                journal,
            )

        return snapshot