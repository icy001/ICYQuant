from services.ai import TradingDecisionEngine


def test_decision_engine():

    engine = TradingDecisionEngine()

    decision = engine.decide(
        "NVDA",
        "bullish trend"
    )

    assert decision.symbol == "NVDA"

    assert decision.action == "HOLD"