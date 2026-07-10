from copy import deepcopy
from dataclasses import dataclass, field
from typing import Dict

from .rules import RiskRule
from .context import RiskContext
from .result import RiskResult, RiskDecision


@dataclass
class RiskLimits:
    max_position_size: float = 1000.0
    max_order_quantity: float = 500.0
    max_daily_trades: int = 100
    max_exposure: float = 0.5
    max_drawdown: float = 0.03
    min_cash_balance: float = 1000.0
    position_limits: Dict[str, float] = field(default_factory=lambda: {"NVDA": 1000, "GC": 20})


class PositionLimitRule(RiskRule):
    def __init__(self, max_weight: float = 0.20):
        self.max_weight = max_weight

    def evaluate(self, order, context: RiskContext) -> RiskResult:
        if context.account_equity <= 0:
            return RiskResult(RiskDecision.PASS)

        current_value = context.account_equity

        if context.market_snapshot:
            bar = context.market_snapshot.get(order.symbol)
            price = bar.close if bar else 0.0
        else:
            price = order.price

        if price <= 0:
            return RiskResult(RiskDecision.PASS)

        order_value = abs(order.quantity) * price
        target_weight = order_value / current_value

        if target_weight > self.max_weight:
            max_quantity = (self.max_weight * current_value) / price
            modified_order = deepcopy(order)
            modified_order.quantity = max_quantity if order.quantity > 0 else -max_quantity

            return RiskResult(
                decision=RiskDecision.MODIFY,
                message=f"Position weight {target_weight:.2%} exceeds max {self.max_weight:.2%}, modified quantity from {order.quantity} to {modified_order.quantity}",
                modified_order=modified_order
            )

        return RiskResult(RiskDecision.PASS)