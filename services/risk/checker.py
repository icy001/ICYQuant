from typing import Dict, List

from .limits import RiskLimits
from .rules import CashBalanceRule, ExposureRule, OrderQuantityRule, PositionSizeRule


class RiskChecker:
    def __init__(self, limits: RiskLimits = None) -> None:
        self.limits = limits or RiskLimits()
        self.rules = [
            PositionSizeRule(self.limits.max_position_size),
            CashBalanceRule(self.limits.min_cash_balance),
            OrderQuantityRule(self.limits.max_order_quantity),
            ExposureRule(self.limits.max_exposure),
        ]

    def check(self, order, portfolio) -> Dict[str, bool]:
        results = {}
        passed = True

        for rule in self.rules:
            result = rule.check(order, portfolio)
            results.update(result)
            if "reason" in result and result["reason"]:
                passed = False

        results["overall"] = passed
        return results

    def check_all(self, orders: List, portfolio) -> List[Dict]:
        return [self.check(order, portfolio) for order in orders]
