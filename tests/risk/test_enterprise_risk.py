from services.risk import (
    RiskDecisionEngine,
)


def test_risk_decision():
    engine = RiskDecisionEngine()

    result = engine.decide(
        0.35,
    )

    assert result.approved is True