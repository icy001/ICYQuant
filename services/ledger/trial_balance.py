"""
Trial balance verification.
"""

from __future__ import annotations

from decimal import Decimal

from .journal import Journal
from .report import TrialBalanceReport


class TrialBalanceService:
    def verify(
        self,
        journals: list[Journal],
    ) -> TrialBalanceReport:
        debit = Decimal("0")
        credit = Decimal("0")

        for journal in journals:
            debit += journal.debit_total
            credit += journal.credit_total

        return TrialBalanceReport(
            debit_total=debit,
            credit_total=credit,
            journal_count=len(journals),
            balanced=(debit == credit),
        )