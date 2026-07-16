"""
Trial balance report.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class TrialBalanceReport:
    debit_total: Decimal
    credit_total: Decimal
    journal_count: int
    balanced: bool