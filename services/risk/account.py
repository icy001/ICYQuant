"""
Account risk information.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class AccountRiskInfo:
    account_id: str
    equity: Decimal
    used_margin: Decimal

    @property
    def available_margin(self) -> Decimal:
        return self.equity - self.used_margin