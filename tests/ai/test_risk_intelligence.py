from services.ai import RiskContext


def test_risk_context():

    context = RiskContext(
        "PF001",
        ["NVDA"],
        {},
        {},
    )

    assert context.portfolio_id == "PF001"