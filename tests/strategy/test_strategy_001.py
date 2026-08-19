"""Unit tests for Strategy 001 (NVDA 15m dual moving-average cross)."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from research.data.bar import Bar
from research.strategy.signal import SignalType
from research.strategy.strategy_001 import (
    DEFAULT_LONG_WINDOW,
    DEFAULT_SHORT_WINDOW,
    STRATEGY_ID,
    STRATEGY_NAME,
    Strategy001,
)


def _bar(close: float, index: int) -> Bar:
    return Bar(
        symbol="NVDA",
        timestamp=datetime(2025, 4, 1, 9, 30) + timedelta(minutes=15 * index),
        open=close,
        high=close,
        low=close,
        close=close,
        volume=1_000_000,
    )


def _feed(closes: list[float], strategy: Strategy001) -> list[SignalType]:
    """Feed closes into the strategy, warming up the MA buffers first."""
    warm = max(DEFAULT_LONG_WINDOW, DEFAULT_SHORT_WINDOW) + 5
    warmup = [closes[0]] * warm
    feed = warmup + closes
    types: list[SignalType] = []
    for i, c in enumerate(feed):
        sig = strategy.on_bar(_bar(c, i))
        if i >= warm - 1:  # warmup consumes the warm bars; then real closes
            types.append(sig.signal_type)
    return types


def test_metadata():
    s = Strategy001(symbol="NVDA")
    assert s.strategy_id == STRATEGY_ID == "S001"
    assert STRATEGY_NAME.startswith("Strategy 001")
    assert s.symbol == "NVDA"


def test_warmup_emits_hold():
    s = Strategy001(symbol="NVDA")
    closes = [100.0] * (DEFAULT_LONG_WINDOW + 5)
    types = _feed(closes, s)
    assert all(t == SignalType.HOLD for t in types)


def test_golden_cross_emits_buy():
    s = Strategy001(symbol="NVDA")
    # flat, then a sharp uptrend -> short MA crosses above long MA
    closes = [100.0] * (DEFAULT_LONG_WINDOW + 10) + [
        100.0 + 0.5 * i for i in range(1, DEFAULT_LONG_WINDOW + 20)
    ]
    types = _feed(closes, s)
    assert SignalType.BUY in types


def test_death_cross_emits_sell():
    s = Strategy001(symbol="NVDA")
    # flat, then a sharp downtrend -> short MA crosses below long MA
    closes = [100.0] * (DEFAULT_LONG_WINDOW + 10) + [
        100.0 - 0.5 * i for i in range(1, DEFAULT_LONG_WINDOW + 20)
    ]
    types = _feed(closes, s)
    assert SignalType.SELL in types


def test_no_duplicate_signals_while_trending():
    s = Strategy001(symbol="NVDA")
    # monotonic uptrend: only one BUY at the crossover, then HOLD
    closes = [100.0] * (DEFAULT_LONG_WINDOW + 10) + [
        100.0 + 0.3 * i for i in range(1, DEFAULT_LONG_WINDOW + 30)
    ]
    types = _feed(closes, s)
    assert types.count(SignalType.BUY) == 1
    assert SignalType.SELL not in types


@pytest.mark.parametrize("short_window,long_window", [(20, 60), (10, 30), (5, 20)])
def test_custom_windows_construct(short_window, long_window):
    s = Strategy001(symbol="NVDA", short_window=short_window, long_window=long_window)
    assert s.short.maxlen == short_window
    assert s.long.maxlen == long_window
