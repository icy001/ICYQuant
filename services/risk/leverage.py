from .rules import RiskRule
from .context import RiskContext
from .result import RiskResult, RiskDecision


class LeverageRule(RiskRule):
    def __init__(self, max_gross_exposure: float = 2.0, max_net_exposure: float = 1.0):
        self.max_gross_exposure = max_gross_exposure
        self.max_net_exposure = max_net_exposure

    def evaluate(self, order, context: RiskContext) -> RiskResult:
        if context.account_equity <= 0:
            return RiskResult(RiskDecision.PASS)

        if context.market_snapshot:
            bar = context.market_snapshot.get(order.symbol)
            order_price = bar.close if bar else order.price
        else:
            order_price = order.price

        order_value = abs(order.quantity) * order_price

        leverage = order_value / context.account_equity if context.account_equity > 0 else 0

        if leverage > self.max_gross_exposure:
            return RiskResult(
                decision=RiskDecision.REJECT,
                message=f"Gross leverage {leverage:.2f}x exceeds max {self.max_gross_exposure:.2f}x"
            )

        return RiskResult(RiskDecision.PASS)