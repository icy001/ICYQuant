"""
Risk request model.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class RiskRequest:
    account_id: str
    symbol: str
    quantity: Decimal
    price: Decimal