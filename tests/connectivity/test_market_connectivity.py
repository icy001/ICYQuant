from services.connectivity.market.tick import MarketTick


def test_tick():

    tick = MarketTick(
        "NVDA",
        200,
        1000,
        123456
    )

    assert tick.symbol == "NVDA"