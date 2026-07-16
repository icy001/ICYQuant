"""
ExecutionReport -> Trade mapper.
"""

from __future__ import annotations

from .model import Trade
from .orm import TradeModel


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

    @staticmethod
    def to_model(trade: Trade) -> TradeModel:
        return TradeModel(
            id=trade.trade_id,
            order_id=str(trade.order_id),
            execution_id=trade.execution_id,
            symbol=trade.symbol,
            quantity=trade.quantity,
            price=trade.price,
            commission=trade.commission,
        )

    @staticmethod
    def to_domain(model: TradeModel) -> Trade:
        from uuid import UUID

        trade = Trade(
            order_id=UUID(model.order_id),
            symbol=model.symbol,
            quantity=model.quantity,
            price=model.price,
        )

        trade.trade_id = model.id
        trade.execution_id = model.execution_id
        trade.commission = model.commission
        trade.executed_at = model.created_at

        return trade