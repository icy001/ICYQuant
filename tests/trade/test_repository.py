from services.trade import (
    TradeModel,
    TradeRepository,
)


def test_trade_repository_model():
    repo = TradeRepository(
        session=None,
    )

    assert repo.model is TradeModel