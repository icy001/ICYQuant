"""
Position mapper.
"""

from __future__ import annotations

from .model import Position
from .orm import PositionModel


class PositionMapper:
    @staticmethod
    def to_model(position: Position) -> PositionModel:
        return PositionModel(
            account_id=position.account_id,
            symbol=position.symbol,
            quantity=position.quantity,
            average_cost=position.average_cost,
            realized_pnl=position.realized_pnl,
            version=position.version,
        )

    @staticmethod
    def to_domain(model: PositionModel) -> Position:
        return Position(
            account_id=model.account_id,
            symbol=model.symbol,
            quantity=model.quantity,
            average_cost=model.average_cost,
            realized_pnl=model.realized_pnl,
            version=model.version,
        )