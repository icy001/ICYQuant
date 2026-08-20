"""Deterministic long-only backtest engine for Discovery Lab v1.

Design notes
------------
- **Warm-up aware**: indicators are computed on the *full* bar history once and
  cached per asset (via :class:`~research.discovery.indicators.IndicatorLibrary`),
  so a segment that starts mid-history benefits from pre-segment indicator
  warm-up (no artificial "no signal at the start" hole).
- **No look-ahead**: every signal is evaluated using information available at
  the *current* bar close; the position transition happens at that same close
  (the standard signal-close execution convention). Rolling channels use only
  bars strictly before the current bar.
- **Segment isolation**: the state machine starts flat at the segment's first
  bar.  Train / Validation / OOS segments are evaluated independently; the OOS
  segment is never used to pick parameters (enforced by the engine).
- **Costs always on**: each round trip pays ``2 * one_way_bps`` of notional
  (commission + spread + slippage folded into the per-asset cost model).
- **Daily metrics**: the intraday equity curve is resampled to daily closes
  (last equity of each day) and metrics are annualised with
  ``periods_per_year`` (252) — consistent across assets and timeframes.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Callable, Optional

from ..data.bar import Bar
from .candidate import Candidate
from .cost import CostModel, DEFAULT_COST_MODEL
from .indicators import IndicatorLibrary
from .split import TimeSplit, SEGMENT_TRAIN, SEGMENT_VALIDATION, SEGMENT_OOS

Number = Optional[float]


# --------------------------------------------------------------------------- #
# Result containers                                                            #
# --------------------------------------------------------------------------- #
@dataclass
class Metrics:
    """Performance metrics over one backtest segment."""

    total_return: float = 0.0          # simple return over the segment (0.12 = 12%)
    annual_return: float = 0.0         # annualised (periods_per_year compounding)
    sharpe: float = 0.0                # annualised, daily-resampled
    max_drawdown: float = 0.0          # peak-to-trough, negative number (-0.25 = -25%)
    profit_factor: float = 0.0         # gross profit / gross loss (99.0 if no losses)
    trade_count: int = 0
    avg_holding_bars: float = 0.0
    exposure: float = 0.0              # fraction of bars in market
    turnover: float = 0.0              # number of round trips (full-investment trades)

    def to_dict(self) -> dict[str, object]:
        return {
            "total_return": round(self.total_return, 6),
            "annual_return": round(self.annual_return, 6),
            "sharpe": round(self.sharpe, 4),
            "max_drawdown": round(self.max_drawdown, 6),
            "profit_factor": round(self.profit_factor, 4),
            "trade_count": self.trade_count,
            "avg_holding_bars": round(self.avg_holding_bars, 2),
            "exposure": round(self.exposure, 4),
            "turnover": round(self.turnover, 4),
        }


@dataclass
class TradeRecord:
    entry_ts: datetime
    exit_ts: datetime
    entry_price: float
    exit_price: float
    bars_held: int
    gross_return: float
    net_return: float
    one_way_cost_bps: float


@dataclass
class BacktestResult:
    candidate_id: str
    asset: str
    structure_id: str
    segment: str
    start: Optional[datetime]
    end: Optional[datetime]
    cost_one_way_bps: float
    metrics: Metrics = field(default_factory=Metrics)
    trades: list[TradeRecord] = field(default_factory=list)
    equity_curve: list[tuple[str, float]] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "asset": self.asset,
            "structure_id": self.structure_id,
            "segment": self.segment,
            "start": self.start.isoformat() if self.start else None,
            "end": self.end.isoformat() if self.end else None,
            "cost_one_way_bps": self.cost_one_way_bps,
            "metrics": self.metrics.to_dict(),
            "trade_count": len(self.trades),
        }


# --------------------------------------------------------------------------- #
# Signal evaluators — one entry/exit boolean series per structure.             #
# None indicator values are treated as "condition unavailable" -> no signal.   #
# --------------------------------------------------------------------------- #
SignalFn = Callable[[dict, IndicatorLibrary, list, list, list],
                    tuple[list[bool], list[bool]]]


def _cross_up(series: list[Number], level: float, i: int) -> bool:
    v = series[i]
    if v is None:
        return False
    prev = series[i - 1] if i > 0 else None
    if prev is None:
        return v > level
    return prev <= level and v > level


def _cross_down(series: list[Number], level: float, i: int) -> bool:
    v = series[i]
    if v is None:
        return False
    prev = series[i - 1] if i > 0 else None
    if prev is None:
        return v < level
    return prev >= level and v < level


def _cross_up_series(a: list[Number], b: list[Number], i: int) -> bool:
    va, vb = a[i], b[i]
    if va is None or vb is None:
        return False
    prev_a = a[i - 1] if i > 0 else None
    prev_b = b[i - 1] if i > 0 else None
    if prev_a is None or prev_b is None:
        return va > vb
    return prev_a <= prev_b and va > vb


def _cross_down_series(a: list[Number], b: list[Number], i: int) -> bool:
    va, vb = a[i], b[i]
    if va is None or vb is None:
        return False
    prev_a = a[i - 1] if i > 0 else None
    prev_b = b[i - 1] if i > 0 else None
    if prev_a is None or prev_b is None:
        return va < vb
    return prev_a >= prev_b and va < vb


def _ema_cross(p: dict, lib: IndicatorLibrary, closes, highs, lows):
    fast = lib.ema(closes, p["fast"])
    slow = lib.ema(closes, p["slow"])
    n = len(closes)
    entry, exit_ = [], []
    for i in range(n):
        f, s = fast[i], slow[i]
        entry.append(f is not None and s is not None and f > s)
        exit_.append(f is not None and s is not None and f < s)
    return entry, exit_


def _sma_cross(p: dict, lib: IndicatorLibrary, closes, highs, lows):
    fast = lib.sma(closes, p["fast"])
    slow = lib.sma(closes, p["slow"])
    n = len(closes)
    entry, exit_ = [], []
    for i in range(n):
        f, s = fast[i], slow[i]
        entry.append(f is not None and s is not None and f > s)
        exit_.append(f is not None and s is not None and f < s)
    return entry, exit_


def _ema_supertrend(p: dict, lib: IndicatorLibrary, closes, highs, lows):
    fast = lib.ema(closes, p["fast"])
    slow = lib.ema(closes, p["slow"])
    st = lib.supertrend(highs, lows, closes, p["atr_period"], p["mult"])
    n = len(closes)
    entry, exit_ = [], []
    for i in range(n):
        f, s, t = fast[i], slow[i], st[i]
        trend_ok = t is True
        entry.append(f is not None and s is not None and f > s and trend_ok)
        exit_.append((f is not None and s is not None and f < s) or t is False)
    return entry, exit_


def _ema_adx(p: dict, lib: IndicatorLibrary, closes, highs, lows):
    fast = lib.ema(closes, p["fast"])
    slow = lib.ema(closes, p["slow"])
    adx = lib.adx(highs, lows, closes, p["adx_period"])
    n = len(closes)
    entry, exit_ = [], []
    for i in range(n):
        f, s, a = fast[i], slow[i], adx[i]
        entry.append(f is not None and s is not None and a is not None
                     and f > s and a > p["entry_adx"])
        exit_.append((f is not None and s is not None and f < s)
                     or (a is not None and a < p["exit_adx"]))
    return entry, exit_


def _donchian_lvl(p: dict, lib: IndicatorLibrary, closes, highs, lows):
    upper, middle, lower = lib.donchian(highs, lows, p["period"])
    n = len(closes)
    entry, exit_ = [], []
    for i in range(n):
        c, u, m = closes[i], upper[i], middle[i]
        entry.append(c is not None and u is not None and c > u)
        exit_.append(c is not None and m is not None and c < m)
    return entry, exit_


def _rsi_cross(p: dict, lib: IndicatorLibrary, closes, highs, lows):
    r = lib.rsi(closes, p["period"])
    n = len(closes)
    entry = [_cross_up(r, p["oversold"], i) for i in range(n)]
    exit_ = [_cross_down(r, p["overbought"], i) for i in range(n)]
    return entry, exit_


def _roc_cross(p: dict, lib: IndicatorLibrary, closes, highs, lows):
    r = lib.roc(closes, p["period"])
    n = len(closes)
    entry = [_cross_up(r, 0.0, i) for i in range(n)]
    exit_ = [_cross_down(r, 0.0, i) for i in range(n)]
    return entry, exit_


def _momentum_cross(p: dict, lib: IndicatorLibrary, closes, highs, lows):
    m = lib.momentum(closes, p["period"])
    n = len(closes)
    entry = [_cross_up(m, 0.0, i) for i in range(n)]
    exit_ = [_cross_down(m, 0.0, i) for i in range(n)]
    return entry, exit_


def _macd_cross(p: dict, lib: IndicatorLibrary, closes, highs, lows):
    line, sig, _ = lib.macd(closes, p["fast"], p["slow"], p["signal"])
    n = len(closes)
    entry = [_cross_up_series(line, sig, i) for i in range(n)]
    exit_ = [_cross_down_series(line, sig, i) for i in range(n)]
    return entry, exit_


def _stochastic_cross(p: dict, lib: IndicatorLibrary, closes, highs, lows):
    k, d = lib.stochastic(highs, lows, closes, p["period"])
    n = len(closes)
    entry = [_cross_up(k, p["oversold"], i) for i in range(n)]
    exit_ = [_cross_down(k, p["overbought"], i) for i in range(n)]
    return entry, exit_


def _highlow_breakout(p: dict, lib: IndicatorLibrary, closes, highs, lows):
    rh = lib.rolling_high(highs, p["period"])
    rl = lib.rolling_low(lows, p["period"])
    n = len(closes)
    entry, exit_ = [], []
    for i in range(n):
        c, h, l = closes[i], rh[i], rl[i]
        entry.append(c is not None and h is not None and c > h)
        exit_.append(c is not None and l is not None and c < l)
    return entry, exit_


def _atr_breakout(p: dict, lib: IndicatorLibrary, closes, highs, lows):
    a = lib.atr(highs, lows, closes, p["period"])
    n = len(closes)
    lb = p["lookback"]
    k = p["k"]
    entry, exit_ = [], []
    for i in range(n):
        c = closes[i]
        base = closes[i - lb] if i >= lb else None
        av = a[i]
        entry.append(c is not None and base is not None and av is not None
                     and c > base + k * av)
        exit_.append(c is not None and base is not None and av is not None
                     and c < base - k * av)
    return entry, exit_


def _bollinger_rev(p: dict, lib: IndicatorLibrary, closes, highs, lows):
    upper, middle, lower = lib.bollinger(closes, p["period"], p["k"])
    n = len(closes)
    entry, exit_ = [], []
    for i in range(n):
        c, m, l = closes[i], middle[i], lower[i]
        entry.append(c is not None and l is not None and c < l)
        exit_.append(c is not None and m is not None and c > m)
    return entry, exit_


def _rsi_rev(p: dict, lib: IndicatorLibrary, closes, highs, lows):
    r = lib.rsi(closes, p["period"])
    n = len(closes)
    entry, exit_ = [], []
    for i in range(n):
        v = r[i]
        entry.append(v is not None and v < p["oversold"])
        exit_.append(v is not None and v > p["mid"])
    return entry, exit_


def _ma_rev(p: dict, lib: IndicatorLibrary, closes, highs, lows):
    e = lib.sma(closes, p["entry_period"])
    x = lib.sma(closes, p["exit_period"])
    n = len(closes)
    pct = p["pct"]
    entry, exit_ = [], []
    for i in range(n):
        c, ev, xv = closes[i], e[i], x[i]
        entry.append(c is not None and ev is not None and c < ev * (1.0 - pct))
        exit_.append(c is not None and xv is not None and c > xv)
    return entry, exit_


def _hybrid_ema_rsi(p: dict, lib: IndicatorLibrary, closes, highs, lows):
    fast = lib.ema(closes, p["fast"])
    slow = lib.ema(closes, p["slow"])
    r = lib.rsi(closes, p["rsi_period"])
    n = len(closes)
    entry, exit_ = [], []
    for i in range(n):
        f, s, v = fast[i], slow[i], r[i]
        entry.append(f is not None and s is not None and v is not None
                     and f > s and v > 50.0)
        exit_.append((f is not None and s is not None and f < s)
                     or (v is not None and v < p["exit_level"]))
    return entry, exit_


def _hybrid_ema_adx(p: dict, lib: IndicatorLibrary, closes, highs, lows):
    fast = lib.ema(closes, p["fast"])
    slow = lib.ema(closes, p["slow"])
    adx = lib.adx(highs, lows, closes, p["adx_period"])
    n = len(closes)
    entry, exit_ = [], []
    for i in range(n):
        f, s, a = fast[i], slow[i], adx[i]
        entry.append(f is not None and s is not None and a is not None
                     and f > s and a > 25.0)
        exit_.append((f is not None and s is not None and f < s)
                     or (a is not None and a < 20.0))
    return entry, exit_


def _hybrid_breakout_atr(p: dict, lib: IndicatorLibrary, closes, highs, lows):
    upper, middle, lower = lib.donchian(highs, lows, p["period"])
    a = lib.atr(highs, lows, closes, p["period"])
    a50 = lib.sma(a, 50)
    n = len(closes)
    k = p["k"]
    entry, exit_ = [], []
    for i in range(n):
        c, u, m = closes[i], upper[i], middle[i]
        av, avg = a[i], a50[i]
        entry.append(c is not None and u is not None and av is not None
                     and avg is not None and c > u and av > k * avg)
        exit_.append(c is not None and m is not None and c < m)
    return entry, exit_


EVALUATORS: dict[str, SignalFn] = {
    "trend_ema_cross": _ema_cross,
    "trend_sma_cross": _sma_cross,
    "trend_ema_supertrend": _ema_supertrend,
    "trend_ema_adx": _ema_adx,
    "trend_donchian": _donchian_lvl,
    "momentum_rsi": _rsi_cross,
    "momentum_roc": _roc_cross,
    "momentum_mom": _momentum_cross,
    "momentum_macd": _macd_cross,
    "momentum_stochastic": _stochastic_cross,
    "breakout_donchian": _donchian_lvl,
    "breakout_highlow": _highlow_breakout,
    "breakout_atr": _atr_breakout,
    "meanrev_bollinger": _bollinger_rev,
    "meanrev_rsi": _rsi_rev,
    "meanrev_ma": _ma_rev,
    "hybrid_ema_rsi": _hybrid_ema_rsi,
    "hybrid_ema_adx": _hybrid_ema_adx,
    "hybrid_breakout_atr": _hybrid_breakout_atr,
}

# All supported structure ids (must match spec.STRUCTURES).
KNOWN_STRUCTURES = frozenset(EVALUATORS.keys())


# --------------------------------------------------------------------------- #
# Backtest engine                                                              #
# --------------------------------------------------------------------------- #
class DiscoveryBacktest:
    """Deterministic long-only signal->position->performance backtest."""

    def __init__(self, capital: float = 100_000.0,
                 periods_per_year: int = 252,
                 cost_model: CostModel = DEFAULT_COST_MODEL) -> None:
        self.capital = capital
        self.periods_per_year = periods_per_year
        self.cost_model = cost_model

    # ------------------------------------------------------------------ #
    @staticmethod
    def _range_indices(bars: list[Bar], start: date, end: date) -> tuple[int, int]:
        """First/last inclusive indices for bars within [start, end]."""
        i0, i1 = 0, len(bars)
        for i, b in enumerate(bars):
            d = b.timestamp.date()
            if d < start:
                i0 = i + 1
            if d <= end:
                i1 = i + 1
        return i0, i1

    def _segment_indices(self, bars: list[Bar], split: TimeSplit,
                         segment: str) -> tuple[int, int]:
        start, end = split.spans[segment]
        return self._range_indices(bars, start, end)

    # ------------------------------------------------------------------ #
    def run(self, bars: list[Bar], candidate: Candidate, split: TimeSplit,
            segment: str, library: Optional[IndicatorLibrary] = None,
            one_way_bps: Optional[float] = None,
            start: Optional[date] = None,
            end: Optional[date] = None,
            arrays: Optional[tuple[list, list, list]] = None) -> BacktestResult:
        """Backtest ``candidate`` on ``bars`` restricted to a segment/range.

        Parameters
        ----------
        bars : full history of the asset (indicators warm up before the range).
        candidate : the candidate to evaluate.
        split : sealed TimeSplit used to find the segment's index range
                (ignored when ``start``/``end`` are given).
        segment : 'train' | 'validation' | 'oos' | walk-forward label.
        library : shared IndicatorLibrary (per asset) for caching.
        one_way_bps : optional override; defaults to the per-asset cost model.
        start / end : optional explicit date range (e.g. a walk-forward window).
        arrays : optional prebuilt (closes, highs, lows) lists for ``bars`` —
                 pass the same objects across calls so the indicator cache hits.
        """
        if candidate.structure_id not in EVALUATORS:
            raise ValueError(f"Unknown structure: {candidate.structure_id}")

        lib = library or IndicatorLibrary()
        if one_way_bps is None:
            one_way_bps = self.cost_model.one_way_bps(candidate.asset)

        if arrays is not None:
            closes, highs, lows = arrays
        else:
            closes = [b.close for b in bars]
            highs = [b.high for b in bars]
            lows = [b.low for b in bars]
        if start is not None and end is not None:
            i0, i1 = self._range_indices(bars, start, end)
        else:
            i0, i1 = self._segment_indices(bars, split, segment)
        if i1 <= i0:
            return BacktestResult(
                candidate_id=candidate.candidate_id,
                asset=candidate.asset,
                structure_id=candidate.structure_id,
                segment=segment,
                start=None, end=None,
                cost_one_way_bps=one_way_bps,
            )

        eval_fn = EVALUATORS[candidate.structure_id]
        entry_sig, exit_sig = eval_fn(candidate.parameters, lib, closes, highs, lows)

        # --- state machine (starts flat at the segment boundary) ---------- #
        c = one_way_bps / 10_000.0
        cost_mult = (1.0 - c) ** 2
        equity = self.capital
        equity_per_day: list[tuple[date, float]] = []
        trades: list[TradeRecord] = []
        in_position = False
        entry_idx = 0
        holding_bars_total = 0
        holding_bars = 0
        for i in range(i0, i1):
            if in_position:
                holding_bars += 1
                if exit_sig[i]:
                    gross = closes[i] / closes[entry_idx] - 1.0
                    net = (1.0 + gross) * cost_mult - 1.0
                    equity *= (1.0 + net)
                    trades.append(TradeRecord(
                        entry_ts=bars[entry_idx].timestamp,
                        exit_ts=bars[i].timestamp,
                        entry_price=closes[entry_idx],
                        exit_price=closes[i],
                        bars_held=holding_bars,
                        gross_return=gross,
                        net_return=net,
                        one_way_cost_bps=one_way_bps,
                    ))
                    holding_bars_total += holding_bars
                    holding_bars = 0
                    in_position = False
            elif entry_sig[i]:
                in_position = True
                entry_idx = i
                holding_bars = 0
            # close-out at segment end
            if i == i1 - 1 and in_position:
                gross = closes[i] / closes[entry_idx] - 1.0
                net = (1.0 + gross) * cost_mult - 1.0
                equity *= (1.0 + net)
                trades.append(TradeRecord(
                    entry_ts=bars[entry_idx].timestamp,
                    exit_ts=bars[i].timestamp,
                    entry_price=closes[entry_idx],
                    exit_price=closes[i],
                    bars_held=holding_bars,
                    gross_return=gross,
                    net_return=net,
                    one_way_cost_bps=one_way_bps,
                ))
                holding_bars_total += holding_bars
                holding_bars = 0
                in_position = False
            d = bars[i].timestamp.date()
            if not equity_per_day or equity_per_day[-1][0] != d:
                equity_per_day.append((d, equity))
            else:
                equity_per_day[-1] = (d, equity)

        metrics = self._compute_metrics(
            trades=trades,
            equity_per_day=equity_per_day,
            segment_bars=(i1 - i0),
        )

        return BacktestResult(
            candidate_id=candidate.candidate_id,
            asset=candidate.asset,
            structure_id=candidate.structure_id,
            segment=segment,
            start=bars[i0].timestamp,
            end=bars[i1 - 1].timestamp,
            cost_one_way_bps=one_way_bps,
            metrics=metrics,
            trades=trades,
            equity_curve=[(d.isoformat(), round(eq, 4))
                          for d, eq in equity_per_day],
        )

    # ------------------------------------------------------------------ #
    def _compute_metrics(self, trades: list[TradeRecord],
                         equity_per_day: list[tuple[date, float]],
                         segment_bars: int) -> Metrics:
        m = Metrics()
        m.trade_count = len(trades)
        if m.trade_count:
            m.avg_holding_bars = sum(t.bars_held for t in trades) / m.trade_count
        m.turnover = float(m.trade_count)

        if not equity_per_day:
            return m

        eq = [e for _, e in equity_per_day]
        m.total_return = eq[-1] / eq[0] - 1.0
        days = len(eq)
        if days >= 2:
            m.annual_return = (1.0 + m.total_return) ** (
                self.periods_per_year / days) - 1.0

        # daily returns -> sharpe (annualised)
        rets = [eq[i] / eq[i - 1] - 1.0 for i in range(1, days)]
        if len(rets) >= 2:
            mean = sum(rets) / len(rets)
            var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
            std = math.sqrt(var)
            if std > 0:
                m.sharpe = mean / std * math.sqrt(self.periods_per_year)

        # max drawdown (peak-to-trough on the daily equity)
        peak = eq[0]
        worst = 0.0
        for e in eq:
            if e > peak:
                peak = e
            dd = e / peak - 1.0
            if dd < worst:
                worst = dd
        m.max_drawdown = worst

        # profit factor from trade net returns
        gains = sum(t.net_return for t in trades if t.net_return > 0)
        losses = -sum(t.net_return for t in trades if t.net_return < 0)
        if losses > 0:
            m.profit_factor = gains / losses
        elif gains > 0:
            m.profit_factor = 99.0

        if segment_bars > 0:
            bars_in_market = sum(t.bars_held for t in trades)
            # open trades at the very end may not be counted; approximate via
            # the fraction of segment days with changing equity is overkill —
            # use traded bars.
            m.exposure = min(bars_in_market / segment_bars, 1.0)
        return m
