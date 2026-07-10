from abc import ABC, abstractmethod
from typing import Dict, Optional

from .context import RiskContext
from .result import RiskResult


class RiskRule(ABC):
    @abstractmethod
    def evaluate(self, order, context: RiskContext) -> RiskResult:
        pass


class PositionSizeRule(RiskRule):
    def __init__(self, max_size: float):
        self.max_size = max_size

    def check(self, order, portfolio) -> Dict[str, bool]:
        current_position = portfolio.get_position(order.symbol) or 0
        new_position = current_position + order.quantity if order.side == "BUY" else current_position - order.quantity
        return {
            "position_size": abs(new_position) <= self.max_size,
            "reason": f"Position {order.symbol} would exceed max size {self.max_size}" if abs(new_position) > self.max_size else "",
        }

    def evaluate(self, order, context: RiskContext) -> RiskResult:
        return self.check(order, context.portfolio)


class CashBalanceRule(RiskRule):
    def __init__(self, min_balance: float):
        self.min_balance = min_balance

    def check(self, order, portfolio) -> Dict[str, bool]:
        required_cash = order.quantity * order.price
        has_enough_cash = portfolio.cash >= required_cash + self.min_balance
        return {
            "cash_balance": has_enough_cash,
            "reason": f"Insufficient cash for order" if not has_enough_cash else "",
        }

    def evaluate(self, order, context: RiskContext) -> RiskResult:
        return self.check(order, context.portfolio)


class OrderQuantityRule(RiskRule):
    def __init__(self, max_quantity: float):
        self.max_quantity = max_quantity

    def check(self, order, portfolio) -> Dict[str, bool]:
        return {
            "order_quantity": order.quantity <= self.max_quantity,
            "reason": f"Order quantity exceeds max {self.max_quantity}" if order.quantity > self.max_quantity else "",
        }

    def evaluate(self, order, context: RiskContext) -> RiskResult:
        return self.check(order, context.portfolio)


class ExposureRule(RiskRule):
    def __init__(self, max_exposure: float):
        self.max_exposure = max_exposure

    def check(self, order, portfolio) -> Dict[str, bool]:
        current_value = portfolio.get_total_value()
        order_value = order.quantity * order.price
        new_exposure = order_value / current_value if current_value > 0 else 0
        return {
            "exposure": new_exposure <= self.max_exposure,
            "reason": f"Exposure would exceed {self.max_exposure}" if new_exposure > self.max_exposure else "",
        }

    def evaluate(self, order, context: RiskContext) -> RiskResult:
        return self.check(order, context.portfolio)