"""
Backtest risk engine.
"""

from .risk_result import RiskResult


class BacktestRiskEngine:
    def __init__(
        self,
        position_checker,
        exposure_checker,
        drawdown_guard,
    ):
        self.position_checker = position_checker
        self.exposure_checker = exposure_checker
        self.drawdown_guard = drawdown_guard

    def evaluate(
        self,
        order,
        portfolio,
        rule,
    ):
        if not self.position_checker.check(order.quantity, rule):
            return RiskResult(False, "POSITION_LIMIT")

        return RiskResult(True, None)