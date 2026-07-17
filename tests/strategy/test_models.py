from datetime import datetime
from decimal import Decimal

from services.strategy import (
    SignalType,
    Strategy,
    StrategyConfig,
    StrategySignal,
    StrategyStatus,
)


def test_strategy_model():
    config = StrategyConfig(
        name="ma_cross",
        symbol="AAPL",
        timeframe="1m",
    )

    strategy = Strategy(config)

    signal = StrategySignal(
        symbol="AAPL",
        signal_type=SignalType.BUY,
        price=Decimal("200"),
        timestamp=datetime.utcnow(),
    )

    assert strategy.status == StrategyStatus.CREATED
    assert signal.signal_type == SignalType.BUY