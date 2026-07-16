from decimal import Decimal

from services.risk import (
    AccountRiskInfo,
    RiskContext,
    RiskDecision,
    RiskEngine,
    RiskRequest,
)
from services.risk.rules.max_order_size import (
    MaxOrderSizeRule,
)


def test_max_order_rule():
    engine = RiskEngine(
        [
            MaxOrderSizeRule(
                Decimal("100"),
            )
        ]
    )

    result = engine.evaluate(
        RiskRequest(
            account_id="A",
            symbol="AAPL",
            quantity=Decimal("200"),
            price=Decimal("10"),
        ),
        RiskContext(
            account_id="A",
            symbol="AAPL",
            current_position=Decimal("0"),
            account=AccountRiskInfo(
                account_id="A",
                equity=Decimal("100000"),
                used_margin=Decimal("0"),
            ),
        ),
    )

    assert result.decision == RiskDecision.REJECT