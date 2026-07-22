from datetime import datetime

from services.backtest import (
    TradeRecord,
    TradeRecorder,
    TradeStatistics,
)


def test_trade_statistics():

    recorder = TradeRecorder()

    recorder.record(
        TradeRecord(
            "TRADE-001",
            "AAPL",
            "BUY",
            100,
            180,
            datetime.utcnow(),
        )
    )

    stats = TradeStatistics().calculate(
        recorder.list_all()
    )

    assert stats["trade_count"] == 1