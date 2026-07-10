from .rules import RiskRule
from .context import RiskContext
from .result import RiskResult, RiskDecision


class MaxDrawdownRule(RiskRule):
    def __init__(self, max_drawdown: float = 0.10):
        self.max_drawdown = max_drawdown

    def evaluate(self, order, context: RiskContext) -> RiskResult:
        if context.account_equity <= 0:
            return RiskResult(RiskDecision.PASS)

        max_equity = context.portfolio.max_equity if hasattr(context.portfolio, 'max_equity') else context.account_equity
        if max_equity <= 0:
            return RiskResult(RiskDecision.PASS)

        drawdown = (max_equity - context.account_equity) / max_equity

        if drawdown >= self.max_drawdown:
            return RiskResult(
                decision=RiskDecision.REJECT,
                message=f"Drawdown {drawdown:.2%} exceeds max {self.max_drawdown:.2%}"
            )

        return RiskResult(RiskDecision.PASS)