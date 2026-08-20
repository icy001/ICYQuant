"""Long-short / long-only factor portfolio backtest (net of transaction costs).

Signal construction (sealed in ``factor_spec``):
    factor -> rolling z-score (250 bars, clipped at +/-3)
    -> Schmitt-trigger position:
         flat -> +1 when z > +ENTRY_Z      flat -> -1 when z < -ENTRY_Z
         +1   -> flat when z < +EXIT_Z     -1   -> flat when z > -EXIT_Z
       (hysteresis keeps turnover down; positions change only at bar closes)

Return accounting (delay-1, no look-ahead):
    pos[t] is decided from data up to bar t and earns the return of bar t+1:
        net[t+1] = pos[t] * ret[t+1] - cost * |pos[t+1] - pos[t]|
    where ``ret[t+1] = close[t+1] / close[t] - 1`` and ``cost`` is the
    per-asset one-way fraction (commission + spread + slippage) from the
    strategy line's CostModel.

Metrics follow the strategy line's conventions: Sharpe is computed on
daily-compounded returns and annualised with 252 periods; max drawdown is
peak-to-trough on the daily equity; turnover is the mean |position change|
per bar.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from .factor_spec import ENTRY_Z, EXIT_Z, Z_CLIP, Z_WINDOW
from .operators import Number


# --------------------------------------------------------------------------- #
# Signal                                                                       #
# --------------------------------------------------------------------------- #
def rolling_zscore(x: list[Number], window: int = Z_WINDOW,
                   clip: float = Z_CLIP) -> list[Number]:
    """Causal rolling z-score of the factor."""
    n = len(x)
    out: list[Number] = [None] * n
    if window < 2:
        return out
    # incremental mean/var (Welford-free, two-pass on sums)
    s = 0.0
    s2 = 0.0
    count = 0
    q: list[Number] = []
    for i in range(n):
        v = x[i]
        q.append(v)
        if v is not None:
            s += v
            s2 += v * v
            count += 1
        if len(q) > window:
            old = q.pop(0)
            if old is not None:
                s -= old
                s2 -= old * old
                count -= 1
        if len(q) == window and count == window:
            mean = s / window
            var = s2 / window - mean * mean
            if var > 0 and v is not None:
                z = (v - mean) / math.sqrt(var)
                out[i] = max(-clip, min(clip, z))
    return out


def positions_from_z(z: list[Number], entry: float = ENTRY_Z,
                     exit_: float = EXIT_Z) -> list[float]:
    """Schmitt-trigger positions: -1 / 0 / +1 with hysteresis."""
    pos: list[float] = []
    cur = 0.0
    for v in z:
        if v is None:
            pos.append(cur)
            continue
        if cur == 0.0:
            if v > entry:
                cur = 1.0
            elif v < -entry:
                cur = -1.0
        elif cur > 0:
            if v < exit_:
                cur = 0.0
        else:  # cur < 0
            if v > -exit_:
                cur = 0.0
        pos.append(cur)
    return pos


def orient_positions(positions: list[float],
                     train_ic: Optional[float]) -> tuple[list[float], float]:
    """Orient the long-short portfolio by the sign of the **train** IC.

    The IC checks are direction-agnostic (|IC|), so the portfolio must trade
    in the factor's empirically measured direction — otherwise every
    negative-IC factor would lose by construction.  The orientation is
    decided on the train segment only and never sees validation / OOS data
    (standard factor-research practice: the sign is part of what is learned
    in-sample).

    Returns ``(oriented_positions, orientation)`` where ``orientation`` is
    +1.0, -1.0 or 0.0 (0 = no measurable train direction -> flat, fail
    closed downstream).
    """
    if train_ic is None or train_ic == 0:
        return [0.0] * len(positions), 0.0
    s = 1.0 if train_ic > 0 else -1.0
    return [p * s for p in positions], s


# --------------------------------------------------------------------------- #
# Return stream                                                                #
# --------------------------------------------------------------------------- #
def net_returns(closes: list[Number], positions: list[float],
                one_way_fraction: float) -> list[Optional[float]]:
    """``net[t] = pos[t-1] * ret[t] - cost * |pos[t] - pos[t-1]|``."""
    n = len(closes)
    out: list[Optional[float]] = [None] * n
    for t in range(1, n):
        c0, c1 = closes[t - 1], closes[t]
        if c0 is None or c1 is None or c0 == 0:
            continue
        ret = c1 / c0 - 1.0
        gross = positions[t - 1] * ret
        cost = one_way_fraction * abs(positions[t] - positions[t - 1])
        out[t] = gross - cost
    return out


# --------------------------------------------------------------------------- #
# Metrics                                                                      #
# --------------------------------------------------------------------------- #
@dataclass
class PortfolioMetrics:
    total_return: float = 0.0
    sharpe: float = 0.0
    max_drawdown: float = 0.0
    turnover_per_bar: float = 0.0
    trade_count: int = 0
    exposure: float = 0.0
    bars: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "total_return": round(self.total_return, 6),
            "sharpe": round(self.sharpe, 4),
            "max_drawdown": round(self.max_drawdown, 6),
            "turnover_per_bar": round(self.turnover_per_bar, 6),
            "trade_count": self.trade_count,
            "exposure": round(self.exposure, 4),
            "bars": self.bars,
        }


def portfolio_metrics(dates: list[date],
                      net_rets: list[Optional[float]],
                      positions: list[float],
                      idx: list[int],
                      periods_per_year: int = 252) -> PortfolioMetrics:
    """Metrics over the segment's bar positions ``idx``.

    Sharpe: daily-compounded returns (per calendar day) annualised at 252 —
    the same convention as the strategy backtest line.
    """
    m = PortfolioMetrics(bars=len(idx))
    if not idx:
        return m

    # compounded segment return
    eq = 1.0
    for t in idx:
        r = net_rets[t]
        if r is not None:
            eq *= (1.0 + r)
    m.total_return = eq - 1.0

    # within-day compounded bar returns -> daily returns
    # (the daily return of day k is prod(1 + r_bar) - 1 over that day's bars)
    cur_day: Optional[date] = None
    day_ret: list[float] = []
    day_prod: Optional[float] = None
    for t in idx:
        r = net_rets[t]
        d = dates[t]
        if d != cur_day:
            if day_prod is not None:
                day_ret.append(day_prod - 1.0)
            cur_day = d
            day_prod = 1.0
        if r is not None and day_prod is not None:
            day_prod *= (1.0 + r)
    if day_prod is not None:
        day_ret.append(day_prod - 1.0)

    if len(day_ret) >= 2:
        mean = sum(day_ret) / len(day_ret)
        var = sum((r - mean) ** 2 for r in day_ret) / (len(day_ret) - 1)
        std = math.sqrt(var)
        if std > 0:
            m.sharpe = mean / std * math.sqrt(periods_per_year)

    # cumulative daily equity -> max drawdown
    eq = 1.0
    peak = 1.0
    worst = 0.0
    for r in day_ret:
        eq *= (1.0 + r)
        if eq > peak:
            peak = eq
        if peak > 0:
            dd = eq / peak - 1.0
            if dd < worst:
                worst = dd
    m.max_drawdown = worst

    # turnover / exposure / trades over the segment
    changes = 0.0
    prev: Optional[float] = None
    for t in idx:
        p = positions[t]
        if prev is not None:
            changes += abs(p - prev)
        prev = p
    m.turnover_per_bar = changes / len(idx) if idx else 0.0
    m.trade_count = int(round(changes / 2.0))  # entries + exits ~ changes/2
    in_market = sum(1 for t in idx if positions[t] != 0.0)
    m.exposure = in_market / len(idx)
    return m
