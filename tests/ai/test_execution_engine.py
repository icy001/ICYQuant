from services.ai import MarketImpactModel


def test_market_impact():

    model = MarketImpactModel()

    impact = model.predict(
        100,
        1000,
    )

    assert impact == 0.1