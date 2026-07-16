"""
Order -> RiskRequest mapper.
"""

from __future__ import annotations

from .model import RiskRequest


class RiskRequestMapper:
    @staticmethod
    def from_order(order) -> RiskRequest:
        return RiskRequest(
            account_id=order.account_id,
            symbol=order.symbol,
            quantity=order.quantity,
            price=order.price,
        )