"""Indicator Library for Strategy Discovery Lab v1.

Pure-Python (no pandas/numpy) implementations of the technical indicators used
by the Discovery structures. Every indicator returns a list aligned with the
input (same length); warm-up values are ``None``.

Conventions
-----------
- Indicators consume plain ``float`` sequences (close / high / low).
- Output ``None`` marks "not enough history"; signal evaluation must treat
  ``None`` as "condition unavailable" (never as False — see backtest.py).
- Smoothing follows Wilder's RMA (period-first-then-exponential) wherever the
  canonical definition uses it (ATR / ADX / RSI), matching the classic
  TradingView semantics used by the Supertrend definition.

No look-ahead: rolling channels (Donchian / rolling high-low) only use bars
strictly *before* the current bar.
"""
from __future__ import annotations

import math
from typing import Callable, Optional, Sequence

Number = Optional[float]
Series = Sequence[Number]


# --------------------------------------------------------------------------- #
# Moving averages                                                              #
# --------------------------------------------------------------------------- #
def sma(values: Series, period: int) -> list[Number]:
    """Simple moving average; ``None`` for the first ``period - 1`` bars."""
    out: list[Number] = [None] * len(values)
    if period <= 0 or len(values) < period:
        return out
    window = 0.0
    for i, v in enumerate(values):
        if v is None:
            continue
        window += v
        if i >= period:
            prev = values[i - period]
            if prev is not None:
                window -= prev
            else:  # pragmatic: recompute window when a None falls out
                window = sum(v for v in values[i - period + 1: i + 1] if v is not None)
        if i >= period - 1:
            out[i] = window / period
    return out


def ema(values: Series, period: int) -> list[Number]:
    """Exponential moving average (seed = SMA of first ``period`` values)."""
    out: list[Number] = [None] * len(values)
    n = len(values)
    if period <= 0 or n < period:
        return out
    k = 2.0 / (period + 1.0)
    seed_sum = 0.0
    for i in range(period):
        v = values[i]
        if v is None:
            return out  # insufficient clean history for the seed
        seed_sum += v
    prev = seed_sum / period
    out[period - 1] = prev
    for i in range(period, n):
        v = values[i]
        if v is None:
            continue
        prev = v * k + prev * (1.0 - k)
        out[i] = prev
    return out


# --------------------------------------------------------------------------- #
# Wilder helpers                                                               #
# --------------------------------------------------------------------------- #
def _wilder_rma(values: Series, period: int) -> list[Number]:
    """Wilder's running moving average (SMA seed then ``(prev*(n-1)+cur)/n``)."""
    out: list[Number] = [None] * len(values)
    n = len(values)
    if period <= 0 or n < period:
        return out
    seed_sum = 0.0
    for i in range(period):
        v = values[i]
        if v is None:
            return out
        seed_sum += v
    prev = seed_sum / period
    out[period - 1] = prev
    for i in range(period, n):
        v = values[i]
        if v is None:
            continue
        prev = (prev * (period - 1) + v) / period
        out[i] = prev
    return out


def _crossed_above(a: float, b: float, prev_a: Optional[float], prev_b: Optional[float]) -> bool:
    """True when ``a`` crossed up through ``b`` at the current bar."""
    if prev_a is None or prev_b is None:
        return a > b
    return prev_a <= prev_b and a > b


def _crossed_below(a: float, b: float, prev_a: Optional[float], prev_b: Optional[float]) -> bool:
    if prev_a is None or prev_b is None:
        return a < b
    return prev_a >= prev_b and a < b


# --------------------------------------------------------------------------- #
# Volatility                                                                   #
# --------------------------------------------------------------------------- #
def atr(highs: Series, lows: Series, closes: Series, period: int) -> list[Number]:
    """Average True Range (Wilder)."""
    n = len(closes)
    trs: list[float] = [None] * n  # type: ignore[list-item]
    for i in range(n):
        h, l, c = highs[i], lows[i], closes[i]
        if h is None or l is None or c is None:
            continue
        if i == 0:
            trs[i] = h - l
            continue
        pc = closes[i - 1]
        if pc is None:
            continue
        trs[i] = max(h - l, abs(h - pc), abs(l - pc))
    return _wilder_rma(trs, period)  # type: ignore[arg-type]


def _hl2(highs: Series, lows: Series) -> list[Number]:
    return [None if h is None or l is None else (h + l) / 2.0
            for h, l in zip(highs, lows)]


def supertrend(highs: Series, lows: Series, closes: Series,
               period: int, multiplier: float) -> list[Number]:
    """Supertrend direction: ``True`` = bullish, ``False`` = bearish, ``None`` warm-up.

    Uses the classic definition: final upper/lower bands ratchet from the
    basic bands while price stays inside; the direction flips only on a close
    beyond the prior final band.
    """
    n = len(closes)
    direction: list[Number] = [None] * n
    a = atr(highs, lows, closes, period)
    mid = _hl2(highs, lows)
    final_upper: Optional[float] = None
    final_lower: Optional[float] = None
    trend: Optional[bool] = None
    for i in range(n):
        if a[i] is None or mid[i] is None or closes[i] is None:
            continue
        basic_upper = mid[i] + multiplier * a[i]  # type: ignore[operator]
        basic_lower = mid[i] - multiplier * a[i]  # type: ignore[operator]
        if final_upper is None:
            final_upper = basic_upper
            final_lower = basic_lower
            trend = True if closes[i] > final_upper else False  # type: ignore[operator]
            direction[i] = trend
            continue
        prev_close = closes[i - 1]
        if prev_close is None:
            direction[i] = trend
            continue
        final_upper = (basic_upper if (basic_upper < final_upper or prev_close > final_upper)
                       else final_upper)
        final_lower = (basic_lower if (basic_lower > final_lower or prev_close < final_lower)
                       else final_lower)
        if closes[i] > final_upper:  # type: ignore[operator]
            trend = True
        elif closes[i] < final_lower:  # type: ignore[operator]
            trend = False
        direction[i] = trend
    return direction


def bollinger(closes: Series, period: int, k: float) -> tuple[list[Number], list[Number], list[Number]]:
    """(upper, middle, lower) Bollinger bands; population stdev."""
    n = len(closes)
    mid = sma(closes, period)
    upper: list[Number] = [None] * n
    lower: list[Number] = [None] * n
    for i in range(period - 1, n):
        m = mid[i]
        if m is None:
            continue
        window = [closes[j] for j in range(i - period + 1, i + 1)
                  if closes[j] is not None]
        if len(window) < period:
            continue
        mean = sum(window) / period
        var = sum((x - mean) ** 2 for x in window) / period
        sd = math.sqrt(var)
        upper[i] = mean + k * sd
        lower[i] = mean - k * sd
    return upper, mid, lower


def historical_volatility(closes: Series, period: int) -> list[Number]:
    """Rolling stdev of close-to-close log returns (not annualised)."""
    n = len(closes)
    out: list[Number] = [None] * n
    for i in range(period + 1, n):
        c = closes[i]
        if c is None:
            continue
        rets: list[float] = []
        valid = True
        for j in range(i - period + 1, i + 1):
            cj, cp = closes[j], closes[j - 1]
            if cj is None or cp is None or cp == 0:
                valid = False
                break
            rets.append(math.log(cj / cp))
        if not valid or len(rets) < period:
            continue
        mean = sum(rets) / len(rets)
        var = sum((r - mean) ** 2 for r in rets) / len(rets)
        out[i] = math.sqrt(var)
    return out


# --------------------------------------------------------------------------- #
# Momentum                                                                     #
# --------------------------------------------------------------------------- #
def rsi(closes: Series, period: int) -> list[Number]:
    """Relative Strength Index (Wilder smoothing)."""
    n = len(closes)
    gains: list[float] = [None] * n  # type: ignore[list-item]
    losses: list[float] = [None] * n  # type: ignore[list-item]
    for i in range(1, n):
        c, p = closes[i], closes[i - 1]
        if c is None or p is None:
            continue
        diff = c - p
        gains[i] = max(diff, 0.0)
        losses[i] = max(-diff, 0.0)
    avg_gain = _wilder_rma(gains, period)  # type: ignore[arg-type]
    avg_loss = _wilder_rma(losses, period)  # type: ignore[arg-type]
    out: list[Number] = [None] * n
    for i in range(n):
        ag, al = avg_gain[i], avg_loss[i]
        if ag is None or al is None:
            continue
        if al == 0:
            out[i] = 100.0
        else:
            rs = ag / al
            out[i] = 100.0 - 100.0 / (1.0 + rs)
    return out


def roc(closes: Series, period: int) -> list[Number]:
    """Rate of change in percent: ``(close/close[n] - 1) * 100``."""
    n = len(closes)
    out: list[Number] = [None] * n
    for i in range(period, n):
        c, p = closes[i], closes[i - period]
        if c is None or p is None or p == 0:
            continue
        out[i] = (c / p - 1.0) * 100.0
    return out


def momentum(closes: Series, period: int) -> list[Number]:
    """Momentum: ``close - close[n]``."""
    n = len(closes)
    out: list[Number] = [None] * n
    for i in range(period, n):
        c, p = closes[i], closes[i - period]
        if c is None or p is None:
            continue
        out[i] = c - p
    return out


def macd(closes: Series, fast: int, slow: int, signal: int) -> tuple[list[Number], list[Number], list[Number]]:
    """(macd_line, signal_line, histogram)."""
    ema_f = ema(closes, fast)
    ema_s = ema(closes, slow)
    n = len(closes)
    macd_line: list[Number] = [None] * n
    for i in range(n):
        f, s = ema_f[i], ema_s[i]
        if f is None or s is None:
            continue
        macd_line[i] = f - s
    sig = sma([x if x is not None else 0.0 for x in macd_line], signal)
    # keep None alignment: signal is only valid where macd_line had signal bars
    sig_line: list[Number] = [None] * n
    for i in range(signal - 1, n):
        if macd_line[i] is None:
            sig_line[i] = None
        else:
            sig_line[i] = sig[i]
    hist: list[Number] = [None] * n
    for i in range(n):
        m, s = macd_line[i], sig_line[i]
        if m is None or s is None:
            continue
        hist[i] = m - s
    return macd_line, sig_line, hist


def stochastic(highs: Series, lows: Series, closes: Series,
               period: int, smooth: int = 3) -> tuple[list[Number], list[Number]]:
    """(%K, %D) stochastic oscillator."""
    n = len(closes)
    k: list[Number] = [None] * n
    for i in range(period - 1, n):
        c = closes[i]
        hh = max(highs[j] for j in range(i - period + 1, i + 1) if highs[j] is not None)
        ll = min(lows[j] for j in range(i - period + 1, i + 1) if lows[j] is not None)
        if c is None or hh is None or ll is None or hh == ll:
            continue
        k[i] = (c - ll) / (hh - ll) * 100.0
    d = sma([x if x is not None else 0.0 for x in k], smooth)
    d_line: list[Number] = [None] * n
    for i in range(smooth - 1, n):
        if k[i] is None:
            d_line[i] = None
        else:
            d_line[i] = d[i]
    return k, d_line


# --------------------------------------------------------------------------- #
# Trend strength                                                               #
# --------------------------------------------------------------------------- #
def adx(highs: Series, lows: Series, closes: Series, period: int) -> list[Number]:
    """Average Directional Index (Wilder)."""
    n = len(closes)
    trs: list[float] = [0.0] * n
    plus_dm: list[float] = [0.0] * n
    minus_dm: list[float] = [0.0] * n
    for i in range(1, n):
        h, l, c = highs[i], lows[i], closes[i]
        ph, pl = highs[i - 1], lows[i - 1]
        if h is None or l is None or ph is None or pl is None:
            continue
        pc = closes[i - 1]
        if pc is None:
            continue
        trs[i] = max(h - l, abs(h - pc), abs(l - pc))
        up = h - ph
        down = pl - l
        plus_dm[i] = up if (up > down and up > 0) else 0.0
        minus_dm[i] = down if (down > up and down > 0) else 0.0
    tr_rma = _wilder_rma(trs, period)  # type: ignore[arg-type]
    plus_rma = _wilder_rma(plus_dm, period)  # type: ignore[arg-type]
    minus_rma = _wilder_rma(minus_dm, period)  # type: ignore[arg-type]
    dx: list[float] = [0.0] * n
    for i in range(n):
        tp, tm, t = plus_rma[i], minus_rma[i], tr_rma[i]
        if tp is None or tm is None or t is None or t == 0:
            continue
        pdi = 100.0 * tp / t
        mdi = 100.0 * tm / t
        if pdi + mdi == 0:
            continue
        dx[i] = 100.0 * abs(pdi - mdi) / (pdi + mdi)
    return _wilder_rma(dx, period)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Channels / breakout                                                          #
# --------------------------------------------------------------------------- #
def donchian(highs: Series, lows: Series, period: int) -> tuple[list[Number], list[Number], list[Number]]:
    """(upper, middle, lower) Donchian channel using the previous ``period``
    bars only (no look-ahead into the current bar)."""
    n = len(highs)
    upper: list[Number] = [None] * n
    lower: list[Number] = [None] * n
    middle: list[Number] = [None] * n
    for i in range(period, n):
        hi = [highs[j] for j in range(i - period, i) if highs[j] is not None]
        lo = [lows[j] for j in range(i - period, i) if lows[j] is not None]
        if len(hi) < period or len(lo) < period:
            continue
        u, l = max(hi), min(lo)
        upper[i] = u
        lower[i] = l
        middle[i] = (u + l) / 2.0
    return upper, middle, lower


def rolling_high(highs: Series, period: int) -> list[Number]:
    """Max of the previous ``period`` highs (excludes the current bar)."""
    n = len(highs)
    out: list[Number] = [None] * n
    for i in range(period, n):
        win = [highs[j] for j in range(i - period, i) if highs[j] is not None]
        if len(win) >= period:
            out[i] = max(win)
    return out


def rolling_low(lows: Series, period: int) -> list[Number]:
    """Min of the previous ``period`` lows (excludes the current bar)."""
    n = len(lows)
    out: list[Number] = [None] * n
    for i in range(period, n):
        win = [lows[j] for j in range(i - period, i) if lows[j] is not None]
        if len(win) >= period:
            out[i] = min(win)
    return out


# --------------------------------------------------------------------------- #
# Library facade                                                               #
# --------------------------------------------------------------------------- #
class IndicatorLibrary:
    """Named access to every indicator; caches by (name, params) so a candidate
    backtest never recomputes an identical series twice."""

    def __init__(self) -> None:
        self._cache: dict[tuple, list] = {}

    def _get(self, key: tuple, fn: Callable[[], list]) -> list:
        if key not in self._cache:
            self._cache[key] = fn()
        return self._cache[key]

    def ema(self, closes: Series, period: int) -> list[Number]:
        return self._get(("ema", id(closes), period), lambda: ema(closes, period))

    def sma(self, values: Series, period: int) -> list[Number]:
        return self._get(("sma", id(values), period), lambda: sma(values, period))

    def atr(self, highs: Series, lows: Series, closes: Series, period: int) -> list[Number]:
        key = ("atr", id(closes), period)
        return self._get(key, lambda: atr(highs, lows, closes, period))

    def supertrend(self, highs: Series, lows: Series, closes: Series,
                   period: int, multiplier: float) -> list[Number]:
        key = ("supertrend", id(closes), period, multiplier)
        return self._get(key, lambda: supertrend(highs, lows, closes, period, multiplier))

    def bollinger(self, closes: Series, period: int, k: float):
        key = ("bollinger", id(closes), period, k)
        if key not in self._cache:
            self._cache[key] = bollinger(closes, period, k)
        return self._cache[key]

    def rsi(self, closes: Series, period: int) -> list[Number]:
        return self._get(("rsi", id(closes), period), lambda: rsi(closes, period))

    def roc(self, closes: Series, period: int) -> list[Number]:
        return self._get(("roc", id(closes), period), lambda: roc(closes, period))

    def momentum(self, closes: Series, period: int) -> list[Number]:
        return self._get(("momentum", id(closes), period), lambda: momentum(closes, period))

    def macd(self, closes: Series, fast: int, slow: int, signal: int):
        key = ("macd", id(closes), fast, slow, signal)
        if key not in self._cache:
            self._cache[key] = macd(closes, fast, slow, signal)
        return self._cache[key]

    def stochastic(self, highs: Series, lows: Series, closes: Series, period: int):
        key = ("stochastic", id(closes), period)
        if key not in self._cache:
            self._cache[key] = stochastic(highs, lows, closes, period)
        return self._cache[key]

    def adx(self, highs: Series, lows: Series, closes: Series, period: int) -> list[Number]:
        return self._get(("adx", id(closes), period), lambda: adx(highs, lows, closes, period))

    def donchian(self, highs: Series, lows: Series, period: int):
        key = ("donchian", id(highs), id(lows), period)
        if key not in self._cache:
            self._cache[key] = donchian(highs, lows, period)
        return self._cache[key]

    def rolling_high(self, highs: Series, period: int) -> list[Number]:
        return self._get(("rolling_high", id(highs), period),
                         lambda: rolling_high(highs, period))

    def rolling_low(self, lows: Series, period: int) -> list[Number]:
        return self._get(("rolling_low", id(lows), period),
                         lambda: rolling_low(lows, period))

    def historical_volatility(self, closes: Series, period: int) -> list[Number]:
        return self._get(("hv", id(closes), period),
                         lambda: historical_volatility(closes, period))


__all__ = [
    "sma", "ema", "atr", "supertrend", "bollinger", "historical_volatility",
    "rsi", "roc", "momentum", "macd", "stochastic", "adx", "donchian",
    "rolling_high", "rolling_low", "IndicatorLibrary",
]
