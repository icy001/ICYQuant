from .simple_signal import Signal


class SimpleSignalGenerator:
    def generate(self, strategy, market_data):
        return Signal(
            strategy.strategy_id,
            market_data.symbol,
            "BUY",
            0.8
        )