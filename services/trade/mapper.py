"""
ExecutionReport -> Trade mapper.
"""

from __future__ import annotations

from .model import Trade


class TradeMapper:
    @staticmethod
    def from_execution_report(report, order) -> Trade:
        return Trade(
            order_id=order.order_id,
            symbol=order.symbol,
            quantity=report.filled_quantity,
            price=report.average_price,
            execution_id=getattr(report, "execution_id", None),
        )