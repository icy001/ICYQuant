"""
Trade record model.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class TradeRecord:

    trade_id: str

    symbol: str

    side: str

    quantity: float

    price: float

    timestamp: datetime