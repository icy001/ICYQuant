"""Exp13: EURUSD M5 MOMENTUM system - PREREGISTERED before any result.

WHAT IS NEW HERE
----------------
Prior M5 work in this repo tested REVERSAL (buy after a fall, sell after a
rise). That produced the only statistically strong signal in the project
(M5 reversal: gross 0.3328 pip/trade, zero-cost Sharpe 0.969, t 4.35) but
it is blocked by cost: break-even 0.333 pip vs the account's 1.0 pip.

This tests the OPPOSITE direction: MOMENTUM (buy after a rise, sell after
a fall), on the identical data, identical bar construction, identical
holding grid, identical cost. Because the only thing that changes is the
sign of the position, the result is a direct directional control for the
reversal finding.

EXPECTED SIGN (declared before running, so it is falsifiable)
-------------------------------------------------------------
If the reversal finding is genuine, then under a symmetric signal the
momentum leg is approximately its negative, i.e. negative gross pips per
trade. Combined with a 1.0 pip round trip on a high-frequency M5 grid,
this is expected to be clearly unprofitable. A positive IS result would
contradict that expectation and would need explanation rather than
celebration.

FROZEN DESIGN
-------------
Data       EURUSD M1 -> Beijing -> M5 OHLC
           (identical to eurusd_reversal_v1_m5.load_m5, so results are
            directly comparable to the reversal line)
Sample     2000-05-30 .. 2026-10-02

IS         2000-05-30 .. 2015-12-31
OOS        2016-01-01 .. 2026-10-02

Signal     r_t = close_t / close_{t-N} - 1   over N M5 bars
           momentum direction = sign(r_t)   (long after a rise)
Entry      only when the direction CHANGES (avoids re-entering the same
           state on every bar, which would be a fake trade count)
Holding    exactly H bars, then flat-to-flat re-evaluate
Cost       1.0 pip round trip per trade (= account real terms)

Grid (literature-symmetric with the reversal work; NOT searched)
           (N=12,H=12) (N=12,H=48) (N=48,H=12) (N=48,H=48)

Multiple testing: 4 tests -> Bonferroni alpha 0.05 -> per test 0.0125
           => IS pass needs |t_NW| > 2.498 AND Sharpe > 0.30
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
M1 = REPO / "artifacts/histdata_v9/parsed/eurusd_2000-2026_bars.parquet"
OUT = REPO / "artifacts/research/m5_momentum"

STORED_TO_BEIJING = pd.Timedelta(hours=8)  # matches eurusd_reversal_v1_m5

IS_END = "2015-12-31"
OOS_START = "2016-01-01"

COST_PIPS = 1.0
PIP = 1e-4

BARS_PER_YEAR = 252 * 288          # M5 bars in a 24x5 FX week
IS_T_CRIT = 2.498                  # Bonferroni over 4 tests, two-sided
IS_SHARPE_MIN = 0.30
OOS_T_CRIT = 1.96

GRID = [(12, 12), (12, 48), (48, 12), (48, 48)]


# EURUSD traded roughly 0.82-1.60 over 2000-2026. Anything outside
# [0.5, 2.0] is a corrupt tick, not a price. Raw feed contains one such
# bar (2001-06-08 07:30 close=1965.0001); unfiltered it alone produced a
# spurious -19.6 million pip "trade" that dominated every statistic.
PX_MIN, PX_MAX = 0.5, 2.0


def load_m5() -> pd.DataFrame:
    df = pd.read_parquet(M1, columns=["ts", "open", "high", "low", "close"])
    bj = pd.to_datetime(df["ts"]) + STORED_TO_BEIJING
    df = df.drop(columns=["ts"])
    df.index = bj
    m5 = (df.resample("5min", label="left", origin="start_day")
            .agg(open=("open", "first"), high=("high", "max"),
                 low=("low", "min"), close=("close", "last"))
            .dropna(subset=["open", "high", "low", "close"]))
    good = ((m5["open"].between(PX_MIN, PX_MAX))
            & (m5["high"].between(PX_MIN, PX_MAX))
            & (m5["low"].between(PX_MIN, PX_MAX))
            & (m5["close"].between(PX_MIN, PX_MAX)))
    return m5.loc[good]


def newey_west_t(x: np.ndarray, lag: int) -> float:
    n = len(x)
    if n < 10:
        return float("nan")
    mu = x.mean()
    e = x - mu
    var = (e @ e) / n
    for L in range(1, lag + 1):
        g = (e[L:] @ e[:-L]) / n
        w = 1.0 - L / (lag + 1.0)
        var += 2.0 * w * g
    var = max(var, 1e-18)
    return float(mu / np.sqrt(var / n))


def run(m5: pd.DataFrame, n: int, h: int):
    """Return per-trade net pips and entry index."""
    close = m5["close"].to_numpy(dtype=float)
    idx = m5.index

    r = np.full(len(close), np.nan)
    r[n:] = close[n:] / close[:-n] - 1.0

    direction = np.sign(r)                      # +1 momentum long, -1 short
    direction = np.nan_to_num(direction, nan=0.0)

    # entry only when direction changes
    prev = np.concatenate(([0.0], direction[:-1]))
    entry_mask = (direction != prev) & (direction != 0.0)

    i0 = np.nonzero(entry_mask)[0]
    i0 = i0[i0 + h < len(close)]                # need h bars of forward data
    if len(i0) == 0:
        return pd.Series(dtype=float), pd.DatetimeIndex([])

    dirs = direction[i0]
    entry_px = close[i0]
    exit_px = close[i0 + h]

    gross_pips = dirs * (exit_px - entry_px) / PIP
    net_pips = gross_pips - COST_PIPS
    return pd.Series(net_pips), pd.DatetimeIndex(idx[i0])


def summarise(net: pd.Series, times: pd.DatetimeIndex, years: float) -> dict:
    if len(net) < 200:
        return {}
    mu, sd = net.mean(), net.std(ddof=1)
    tpy = len(net) / years
    sharpe = float(mu / sd * np.sqrt(tpy)) if sd > 0 else np.nan
    return {
        "trades": int(len(net)),
        "trades_per_year": round(float(tpy), 1),
        "gross_pips_per_trade": round(float(mu + COST_PIPS), 4),
        "net_pips_per_trade": round(float(mu), 4),
        "net_pips_per_year": round(float(mu * tpy), 1),
        "ann_sharpe": round(float(sharpe), 3),
        "t_nw": round(float(newey_west_t(net.to_numpy(), lag=10)), 2),
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    m5 = load_m5()
    print("M5 bars: %d   %s -> %s" % (len(m5), m5.index.min(), m5.index.max()))

    span_days = (m5.index.max() - m5.index.min()).days
    years_total = span_days / 365.25
    is_frac = (pd.Timestamp(IS_END) - m5.index.min()).days / span_days
    oos_frac = 1.0 - is_frac
    print("IS ~%.1f yr   OOS ~%.1f yr   cost %.1f pip/round trip"
          % (years_total * is_frac, years_total * oos_frac, COST_PIPS))
    print()
    print("=== IS (pass needs |t_NW| > %.3f AND Sharpe > %.2f) ===" % (IS_T_CRIT, IS_SHARPE_MIN))
    print("%-12s %8s %10s %11s %9s %8s" %
          ("N/H", "trades", "trades/yr", "net_pips/yr", "Sharpe", "t_NW"))
    print("-" * 62)

    cut = pd.Timestamp(IS_END)
    results = {}
    passes = []
    for (n, h) in GRID:
        net, times = run(m5, n, h)
        mask = times <= cut
        s = summarise(net[mask], times[mask], years_total * is_frac)
        label = "N%d_H%d" % (n, h)
        if not s:
            print("%-12s %8s" % (label, "too few"))
            continue
        ok = abs(s["t_nw"]) > IS_T_CRIT and s["ann_sharpe"] > IS_SHARPE_MIN
        s["is_pass"] = ok
        if ok:
            passes.append((n, h))
        print("%-12s %8d %10.1f %+11.1f %9.3f %8.2f  %s"
              % (label, s["trades"], s["trades_per_year"], s["net_pips_per_year"],
                 s["ann_sharpe"], s["t_nw"], "PASS" if ok else "fail"))
        results[label] = {"n": n, "h": h, "is": s}

    print()
    if not passes:
        print("=== No IS pass -> nothing goes to OOS. ===")
    else:
        print("=== OOS for IS passers ===")
        for (n, h) in passes:
            label = "N%d_H%d" % (n, h)
            net, times = run(m5, n, h)
            mask = times > pd.Timestamp(OOS_START)
            o = summarise(net[mask], times[mask], years_total * oos_frac)
            if not o:
                print("%-12s too few OOS trades" % label)
                continue
            same = np.sign(o["ann_sharpe"]) == np.sign(results[label]["is"]["ann_sharpe"])
            o["oos_pass"] = bool(abs(o["t_nw"]) > OOS_T_CRIT and same)
            print("%-12s OOS Sharpe %+.3f  t_NW %+.2f  %s"
                  % (label, o["ann_sharpe"], o["t_nw"],
                     "OOS PASS" if o["oos_pass"] else "OOS fail"))
            results[label]["oos"] = o

    payload = {
        "experiment": "exp13_m5_momentum_preregistered",
        "design_frozen_before_results": True,
        "direction": "momentum (long after a rise) — opposite of the M5 reversal line",
        "expected_sign_declared_in_advance": "negative, if the reversal finding is genuine",
        "data": "EURUSD M1 -> Beijing -> M5 (same construction as reversal_v1)",
        "m5_bars": int(len(m5)),
        "range": [str(m5.index.min()), str(m5.index.max())],
        "is_window": ["2000-05-30", IS_END],
        "oos_window": [OOS_START, "2026-10-02"],
        "cost_pips": COST_PIPS,
        "grid": [{"n": n, "h": h} for (n, h) in GRID],
        "multiple_testing": {
            "method": "Bonferroni, family alpha 0.05 over 4 tests",
            "is_t_crit": IS_T_CRIT,
            "is_sharpe_min": IS_SHARPE_MIN,
            "oos_t_crit": OOS_T_CRIT,
        },
        "results": results,
    }
    out = OUT / "exp13_report.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    print()
    print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
