from services.risk import (
    PreTradeRiskRequest,
    RiskValidator,
    RiskDecisionEngine,
    PreTradeRiskEngine,
)


def test_pre_trade():
    engine = PreTradeRiskEngine(
        RiskValidator(),
        RiskDecisionEngine(),
    )

    result = engine.check(
        PreTradeRiskRequest(
            "ORD-001",
            "ACC-001",
            "AAPL",
            100,
        )
    )

    assert result.passed