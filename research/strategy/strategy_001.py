"""Strategy 001 - NVDA 15m dual moving-average cross.

The first production strategy of the research layer. It reuses the
existing `MovingAverageCrossStrategy` buffer machinery but only emits
signals on an actual crossover (golden cross -> BUY, death cross ->
SELL), instead of re-signaling every bar. Everything downstream
(BacktestRunner, SimulatedBroker, Portfolio, TradeJournal,
PerformanceReport) is untouched.

    STRATEGY_ID:   S001
    Asset:         NVDA
    Timeframe:     15m
    Entry:         short MA crosses above long MA
    Exit:          short MA crosses below long MA
"""
from __future__ import annotations

from research.data.bar import Bar
from research.strategy.signal import Signal, SignalType

from .moving_average import MovingAverageCrossStrategy

STRATEGY_ID = "S001"
STRATEGY_NAME = "Strategy 001 - NVDA 15m Moving Average Cross"
ASSET = "NVDA"
TIMEFRAME = "15m"
DEFAULT_SHORT_WINDOW = 20
DEFAULT_LONG_WINDOW = 60


class Strategy001(MovingAverageCrossStrategy):
    """Dual-MA crossover strategy emitting signals only on crossovers."""

    def __init__(
        self,
        symbol: str = ASSET,
        short_window: int = DEFAULT_SHORT_WINDOW,
        long_window: int = DEFAULT_LONG_WINDOW,
    ):
        super().__init__(
            symbol=symbol,
            short_window=short_window,
            long_window=long_window,
        )
        self._prev_short: float | None = None
        self._prev_long: float | None = None

    @property
    def strategy_id(self) -> str:
        return STRATEGY_ID

    def on_bar(self, bar: Bar) -> Signal:
        self.short.append(bar.close)
        self.long.append(bar.close)

        if len(self.long) < self.long.maxlen:
            return Signal(symbol=self.symbol, signal_type=SignalType.HOLD)

        short_avg = sum(self.short) / len(self.short)
        long_avg = sum(self.long) / len(self.long)

        if self._prev_short is not None and self._prev_long is not None:
            crossed_up = self._prev_short <= self._prev_long and short_avg > long_avg
            crossed_down = self._prev_short >= self._prev_long and short_avg < long_avg

            self._prev_short = short_avg
            self._prev_long = long_avg

            if crossed_up:
                return Signal(
                    symbol=self.symbol,
                    signal_type=SignalType.BUY,
                    strength=1.0,
                )
            if crossed_down:
                return Signal(
                    symbol=self.symbol,
                    signal_type=SignalType.SELL,
                    strength=1.0,
                )
            return Signal(symbol=self.symbol, signal_type=SignalType.HOLD)

        self._prev_short = short_avg
        self._prev_long = long_avg
        return Signal(symbol=self.symbol, signal_type=SignalType.HOLD)
