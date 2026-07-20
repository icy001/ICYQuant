"""
Cash transaction model.
"""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class CashTransaction:
    transaction_id: str
    amount: Decimal
    transaction_type: str