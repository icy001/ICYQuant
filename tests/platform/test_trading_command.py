from services.platform.trading import (
    OrderDecision,
)


def test_order_decision():

    order = OrderDecision(
        "NVDA",
        "BUY",
        100,
        0.9,
    )

    assert order.symbol == "NVDA"