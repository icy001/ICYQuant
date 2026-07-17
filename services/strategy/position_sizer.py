"""
Strategy position sizing engine.
"""

from __future__ import annotations

from decimal import Decimal

from .risk_budget import RiskBudget
from .sizing_result import PositionSizeResult


class PositionSizer:
    def calculate(
        self,
        price: Decimal,
        stop_loss_distance: Decimal,
        budget: RiskBudget,
    ) -> PositionSizeResult:
        risk_amount = budget.account_equity * budget.max_risk_percent

        quantity = risk_amount / stop_loss_distance

        position_value = quantity * price

        if position_value > budget.max_position_value:
            return PositionSizeResult(
                quantity=Decimal("0"),
                risk_amount=risk_amount,
                approved=False,
            )

        return PositionSizeResult(
            quantity=quantity,
            risk_amount=risk_amount,
            approved=True,
        )