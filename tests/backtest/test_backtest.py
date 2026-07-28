from services.backtest import *


def test_backtest():

    events = [

        MarketEvent(

            "NVDA",

            100,

            "2026-01-01"

        )

    ]

    replay = MarketReplay(events)

    service = BacktestService(
        replay
    )

    result = service.run()

    assert len(result) == 1
