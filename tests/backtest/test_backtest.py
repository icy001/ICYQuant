from services.backtest import (
    BacktestFactory,
    BacktestRepository,
    BacktestService,
)


def test_create_backtest():
    service = BacktestService(
        BacktestRepository(),
        BacktestFactory(),
    )

    backtest = service.create(
        "strategy-001"
    )

    assert (
        backtest.strategy_id
        ==
        "strategy-001"
    )