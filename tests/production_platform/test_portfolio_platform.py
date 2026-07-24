from services.platform.portfolio import (
    PortfolioPosition,
)


def test_position():

    position = PortfolioPosition(
        "NVDA",
        10,
        0.1,
    )

    assert position.symbol == "NVDA"