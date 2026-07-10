from .rules import RiskRule
from .context import RiskContext
from .result import RiskResult, RiskDecision


class DailyLossRule(RiskRule):
    def __init__(self, max_daily_loss: float = 0.03):
        self.max_daily_loss = max_daily_loss

    def evaluate(self, order, context: RiskContext) -> RiskResult:
        if context.account_equity <= 0:
            return RiskResult(RiskDecision.PASS)

        daily_pnl = context.daily_pnl
        daily_return = daily_pnl / context.account_equity if context.account_equity > 0 else 0

        if daily_return <= -self.max_daily_loss:
            return RiskResult(
                decision=RiskDecision.REJECT,
                message=f"Daily loss {daily_return:.2%} exceeds max {self.max_daily_loss:.2%}"
            )

        return RiskResult(RiskDecision.PASS)