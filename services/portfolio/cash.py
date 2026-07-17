"""
Portfolio cash snapshot.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class CashBalance:
    currency: str
    available: Decimal
    frozen: Decimal

    @property
    def total(self) -> Decimal:
        return self.available + self.frozen