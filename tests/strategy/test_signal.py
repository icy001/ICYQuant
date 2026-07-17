from services.strategy import (
    SignalGenerator,
    SignalType,
)


def test_generate_signal():
    generator = SignalGenerator()

    signal = generator.generate(
        strategy_id="ma_cross",
        symbol="AAPL",
        signal=SignalType.BUY,
        confidence=0.85,
        reason="moving average crossover",
    )

    assert signal.strategy_id == "ma_cross"
    assert signal.signal == SignalType.BUY
    assert signal.confidence.score == 0.85