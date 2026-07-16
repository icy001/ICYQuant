"""
Position rebuild service.
"""

from __future__ import annotations

from .engine import PositionEngine
from .model import Position
from .snapshot import PositionSnapshot


class PositionRebuildService:
    def __init__(self):
        self.engine = PositionEngine()

    def rebuild(
        self,
        account_id: str,
        symbol: str,
        trades,
    ) -> PositionSnapshot:
        position = Position(
            account_id=account_id,
            symbol=symbol,
        )

        for trade in trades:
            self.engine.apply_trade(
                position,
                trade.quantity,
                trade.price,
            )

        return PositionSnapshot(
            account_id=position.account_id,
            symbol=position.symbol,
            quantity=position.quantity,
            average_cost=position.average_cost,
            realized_pnl=position.realized_pnl,
        )