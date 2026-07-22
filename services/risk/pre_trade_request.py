"""
Pre-trade risk request.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PreTradeRiskRequest:

    order_id: str

    account_id: str

    symbol: str

    quantity: float