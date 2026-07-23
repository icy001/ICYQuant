from services.ai import MarketContext


def test_market_context():

    context = MarketContext(
        "2026-07-22",
        ["NVDA"],
        {},
        {},
        {},
    )

    assert context.symbols == ["NVDA"]