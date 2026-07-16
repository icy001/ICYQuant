from decimal import Decimal

from services.risk import (
    RiskDecision,
    RiskRequest,
    RiskResult,
)


def test_risk_models():
    request = RiskRequest(
        account_id="ACC001",
        symbol="AAPL",
        quantity=Decimal("100"),
        price=Decimal("10"),
    )

    result = RiskResult(
        decision=RiskDecision.APPROVE
    )

    assert request.symbol == "AAPL"
    assert result.decision == RiskDecision.APPROVE