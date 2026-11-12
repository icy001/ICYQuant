"""Exp14: EURUSD M5 REVERSAL at negotiated cost — PREREGISTERED before any result.

WHY THIS EXPERIMENT EXISTS
--------------------------
The M5 reversal is the only candidate in this project that was killed by
cost alone: gross 0.3328 pip/trade, zero-cost Sharpe 0.969, t 4.35, but
break-even 0.333 pip vs the account's 1.0 pip RT -> Sharpe -1.942.

On 2026-11-12 the account terms were renegotiated to 0.15 pip RT, which is
BELOW the 0.16 pip threshold derived in FINAL_REPORT section 5 for reaching
Sharpe ~0.5. This experiment re-runs the reversal on the identical data,
identical bar construction, identical grid, identical IS/OOS split, with
only the cost changed. Everything else is inherited from exp13's machinery
(same load_m5, same price validator, same HAC routine, same statistics).

EXPECTED OUTCOME (declared before running, so it is falsifiable)
----------------------------------------------------------------
If the reversal edge is real and stable, then at 0.15 pip cost the net
pips per trade is about 0.3328 - 0.15 = 0.18 pip, and the IS Sharpe should
land in the 0.3-0.6 band (point estimate ~0.5). A negative IS result, or
an IS Sharpe below 0.30, means the edge did not survive re-testing even at
the negotiated cost and the revival thesis is DEAD — the right response is
to close the line, not to re-tune the grid.

FROZEN DESIGN (do not edit after running)
-----------------------------------------
Data       EURUSD M1 -> Beijing -> M5 OHLC
           (byte-identical loader to exp13 / reversal_v1)
Sample     2000-05-30 .. 2026-10-02

IS         2000-05-30 .. 2015-12-31
OOS        2016-01-01 .. 2026-10-02

Signal     r_t = close_t / close_{t-N} - 1  over N M5 bars
           reversal direction = -sign(r_t)  (sell after a rise)
Entry      only when the direction CHANGES (same rule as exp13)
Holding    exactly H bars, then flat-to-flat re-evaluate
Cost       0.15 pip round trip per trade
           (NEGOTIATED_EURUSD_RT_PIPS in research/discovery/costs.py)

Grid (identical to exp13; NOT searched)
           (N=12,H=12) (N=12,H=48) (N=48,H=12) (N=48,H=48)

Multiple testing: 4 tests -> Bonferroni alpha 0.05 -> per test 0.0125
           => IS pass needs |t_NW| > 2.498 AND Sharpe > 0.30
           => OOS pass needs |t_NW| > 1.96 AND same Sharpe sign as IS

DECISION RULE (declared before running)
---------------------------------------
* Any (N,H) that passes IS AND OOS -> the line is re-opened for a
  small-capital live validation; anything else -> the line stays closed
  permanently (the edge either decayed or never existed).
* No second attempt with a different grid is permitted under this
  experiment number. A new grid would be a new preregistered experiment.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from research.analytics.metrics import calculate_newey_west_t
from research.data.validators import validate_price_range
from research.discovery.costs import NEGOTIATED_EURUSD_RT_PIPS

REPO = Path(__file__).resolve().parents[2]
M1 = REPO / "artifacts/histdata_v9/parsed/eurusd_2000-2026_bars.parquet"
OUT = REPO / "artifacts/research/m5_reversal_revival"

STORED_TO_BEIJING = pd.Timedelta(hours=8)  # matches exp13 / reversal_v1

IS_END = "2015-12-31"
OOS_START = "2016-01-01"

# The newly negotiated account terms (see costs.py; 0.15 <= 0.16 threshold).
COST_PIPS = NEGOTIATED_EURUSD_RT_PIPS
PIP = 1e-4

BARS_PER_YEAR = 252 * 288          # M5 bars in a 24x5 FX week
IS_T_CRIT = 2.498                  # Bonferroni over 4 tests, two-sided
IS_SHARPE_MIN = 0.30
OOS_T_CRIT = 1.96

GRID = [(12, 12), (12, 48), (48, 12), (48, 48)]

# Same corrupt-tick guard as exp13 (raw feed contains 2001-06-08 close=1965).
PX_MIN, PX_MAX = 0.5, 2.0


def load_m5() -> pd.DataFrame:
    """Byte-identical to exp13.load_m5 (and to reversal_v1's construction)."""
    df = pd.read_parquet(M1, columns=["ts", "open", "high", "low", "close"])
    bj = pd.to_datetime(df["ts"]) + STORED_TO_BEIJING
    df = df.drop(columns=["ts"])
    df.index = bj
    m5 = (df.resample("5min", label="left", origin="start_day")
            .agg(open=("open", "first"), high=("high", "max"),
                 low=("low", "min"), close=("close", "last"))
            .dropna(subset=["open", "high", "low", "close"]))
    bad: set[int] = set()
    for col in ("open", "high", "low", "close"):
        bad.update(validate_price_range(m5[col].to_numpy(dtype=float),
                                        (PX_MIN, PX_MAX)))
    if not bad:
        return m5
    keep = np.ones(len(m5), dtype=bool)
    keep[sorted(bad)] = False
    return m5.loc[keep]


def newey_west_t(x: np.ndarray, lag: int) -> float:
    return calculate_newey_west_t(x.tolist(), lag=lag)


def run(m5: pd.DataFrame, n: int, h: int):
    """Return per-trade net pips and entry index — REVERSAL direction.

    Identical mechanics to exp13.run with the position sign flipped:
    sell after a rise, buy after a fall.
    """
    close = m5["close"].to_numpy(dtype=float)
    idx = m5.index

    r = np.full(len(close), np.nan)
    r[n:] = close[n:] / close[:-n] - 1.0

    direction = -np.sign(r)                     # REVERSAL: opposite of exp13
    direction = np.nan_to_num(direction, nan=0.0)

    # entry only when direction changes (same as exp13)
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
    print("IS ~%.1f yr   OOS ~%.1f yr   cost %.2f pip/round trip (negotiated 2026-11-12)"
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
        print("=== No IS pass -> nothing goes to OOS. Revival thesis DEAD. ===")
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
        "experiment": "exp14_m5_reversal_revival_preregistered",
        "design_frozen_before_results": True,
        "direction": "reversal (sell after a rise) — opposite sign of exp13",
        "expected_sign_declared_in_advance": (
            "positive IS Sharpe in the 0.3-0.6 band if the edge survived; "
            "negative or <0.30 Sharpe closes the line permanently"),
        "data": "EURUSD M1 -> Beijing -> M5 (same construction as exp13/reversal_v1)",
        "sample": "2000-05-30 .. 2026-10-02",
        "cost_pips_rt": COST_PIPS,
        "cost_source": "research/discovery/costs.py NEGOTIATED_EURUSD_RT_PIPS (2026-11-12)",
        "split": {"IS_end": IS_END, "OOS_start": OOS_START},
        "grid": GRID,
        "pass_rule": {
            "IS": "|t_NW| > %.3f AND Sharpe > %.2f" % (IS_T_CRIT, IS_SHARPE_MIN),
            "OOS": "|t_NW| > %.2f AND same sign" % OOS_T_CRIT,
        },
        "results": results,
    }
    (OUT / "report.json").write_text(json.dumps(payload, indent=2, default=str))
    print()
    print("wrote %s" % (OUT / "report.json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
