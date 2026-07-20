"""
Cash snapshot.
"""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class CashSnapshot:
    currency: str
    balance: Decimal
    available: Decimal