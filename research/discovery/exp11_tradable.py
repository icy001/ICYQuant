"""Exp11b: restrict the commodity trend panel to actually tradable markets.

RESULT: FALSIFIED once restricted to tradable markets and realistic cost.

    FULL (67 series, mostly NOT tradable)   Sharpe +0.663  t +4.36
    CORE (13 tradable)                      Sharpe +0.379  t +2.48
    CORE at your <=20bp cost                Sharpe +0.187  t +1.23   <-- not significant
    CORE excl. Sugar at 20bp                Sharpe -0.119  t -0.82   <-- loses money

Three independent reasons the CORE number cannot be traded:

1. It is one market. Sugar, world contributes +1.65 of ~2.19 total P&L,
   about 75%. It gets the largest weight because inverse-vol weighting
   favours its low volatility, not because its signal is strong - Sugar
   alone is only t=1.38. Remove it and the portfolio is t=0.86, and at
   20bp it is -0.82.
2. It does not work in the first half of the sample. Sub-period Sharpe is
   -0.08 (1980-1991) and -0.23 (1992-2002), turning positive only from
   2003. A 46-year result whose first 22 years are negative is not a
   persistent edge.
3. Individually, only Copper is significant (t=2.06). All other 12 markets
   are |t| < 1.4; Brent (-0.48) and Soybeans (-0.88) are negative.

Combined with Exp11's finding that the 67-series Sharpe was inflated ~5x by
monthly-average smoothing (3.07 -> 0.66 when entry moves from t+1 to t+2),
commodity trend on this data does not survive at this account's cost.

WHY THIS EXISTS
---------------
Exp11 reported Sharpe 0.663 (entry t+2) across 67 World Bank series. That
number is not usable, because the largest contributors are not tradable:

    DAP (di-ammonium phosphate), TSP (triple superphosphate),
    Potassium chloride, Shrimps Mexican, Fish meal, Plywood, Coal SA

Those five alone were 41.5% of total P&L. A retail CFD broker offers metals,
energy and a handful of softs - not fertiliser, seafood or timber.

So this study re-runs the identical signal on the subset that can actually be
held, and reports the result at the account's real cost (<=20bp round trip).

UNIVERSES
---------
CORE    : offered by essentially every retail CFD broker
EXTENDED: CORE plus base metals and secondary softs that many brokers list

Both are defined explicitly below so the choice is auditable, not fitted.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from exp11_commodity_tsmom import (
    MONTHS_PER_YEAR, build_signals, load_panel, stats,
)

OUT_DIR = Path("artifacts/research/commodity_tsmom")

# --- universes, declared up front -------------------------------------------
CORE = [
    "Crude oil, Brent",
    "Crude oil, WTI",
    "Natural gas, US",
    "Gold",
    "Silver",
    "Copper",
    "Platinum",
    "Wheat, US SRW",
    "Maize",
    "Soybeans",
    "Sugar, world",
    "Coffee, Arabica",
    "Cocoa",
]

EXTENDED = CORE + [
    "Aluminum",
    "Zinc",
    "Nickel",
    "Lead",
    "Iron ore, cfr spot",
    "Soybean oil",
    "Natural gas, Europe",
    "Crude oil, Dubai",
]


def run(px: pd.DataFrame, n: int, h: int, entry_lag: int, cost_bp: float = 0.0):
    """Identical construction to exp11_validation.build, with an optional cost."""
    ret = np.log(px).diff()
    vol = ret.rolling(12, min_periods=6).std().shift(1)
    sig = build_signals(px, n)
    arr = sig.to_numpy()
    out = np.zeros_like(arr)
    nrows, ncols = arr.shape
    for j in range(ncols):
        flat_at = 0
        for i in range(nrows):
            if i < flat_at:
                continue
            s = arr[i, j]
            if s == 0.0 or not np.isfinite(s):
                continue
            start = i + entry_lag
            end = min(start + h, nrows)
            if start < nrows:
                out[start:end, j] = s
            flat_at = end
    pos = pd.DataFrame(out, index=sig.index, columns=sig.columns)
    inv = (1.0 / vol).where(pos != 0)
    w = inv.div(inv.abs().sum(axis=1).replace(0.0, np.nan), axis=0).fillna(0.0)
    pnl = (pos * ret * w).where(pos != 0)
    ew = pnl.sum(axis=1).fillna(0.0).iloc[13:].dropna()
    if cost_bp > 0:
        # h-month holding => 12/h rebalances per year; charge once per rebalance
        ew = ew - (cost_bp / 10_000.0) * (h / h)
    return ew


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    full = load_panel()

    universes = {
        "FULL (67, not all tradable)": list(full.columns),
        "EXTENDED (21)": [c for c in EXTENDED if c in full.columns],
        "CORE (13)": [c for c in CORE if c in full.columns],
    }

    report: dict = {}
    print("Sharpe / t_NW by universe, entry t+2 (clean), N=1 H=1")
    print("=" * 78)
    print("%-32s %6s %10s %8s %10s" % ("universe", "n", "Sharpe", "t_NW", "ann%"))
    print("-" * 78)
    for name, cols in universes.items():
        px = full[cols].copy()
        x = run(px, 1, 1, 2)
        st = stats(x, 1)
        report[name] = {"n_markets": len(cols), **st}
        print("%-32s %6d %+10.3f %+8.2f %+10.2f"
              % (name[:32], len(cols), st["sharpe_ann"], st["t_nw"],
                 st["ann_return_pct"]))

    print("\n--- CORE universe: cost sensitivity at your <=20bp ---")
    px = full[[c for c in CORE if c in full.columns]].copy()
    print("%8s %10s %10s %10s" % ("bp/rt", "Sharpe", "t_NW", "ann net%"))
    print("-" * 42)
    cost_rows = []
    for bp in (0, 5, 10, 15, 20, 25, 30):
        x = run(px, 1, 1, 2, cost_bp=bp)
        st = stats(x, 1)
        cost_rows.append({"bp": bp, **st})
        print("%8d %+10.3f %+10.2f %+10.2f"
              % (bp, st["sharpe_ann"], st["t_nw"], st["ann_return_pct"]))

    print("\n--- CORE universe: sub-period stability (entry t+2, no cost) ---")
    x = run(px, 1, 1, 2)
    per = {}
    print("%-14s %10s %8s" % ("period", "Sharpe", "t_NW"))
    print("-" * 34)
    for a, b in [("1980", "1991"), ("1992", "2002"), ("2003", "2013"), ("2014", "2025")]:
        st = stats(x.loc[a:b], 1)
        per[f"{a}-{b}"] = {"sharpe": st["sharpe_ann"], "t_nw": st["t_nw"]}
        print("%-14s %+10.3f %+8.2f" % (f"{a}-{b}", st["sharpe_ann"], st["t_nw"]))

    print("\n--- CORE universe: IS/OOS (60/40) ---")
    k = int(len(x) * 0.6)
    ist, ost = stats(x.iloc[:k], 1), stats(x.iloc[k:], 1)
    print("  IS  Sharpe %+.3f (t %+.2f)" % (ist["sharpe_ann"], ist["t_nw"]))
    print("  OOS Sharpe %+.3f (t %+.2f)" % (ost["sharpe_ann"], ost["t_nw"]))

    print("\n--- CORE: which markets carry it ---")
    ret = np.log(px).diff()
    vol = ret.rolling(12, min_periods=6).std().shift(1)
    sig = build_signals(px, 1)
    arr = sig.to_numpy()
    out = np.zeros_like(arr)
    for j in range(arr.shape[1]):
        flat = 0
        for i in range(arr.shape[0]):
            if i < flat:
                continue
            s = arr[i, j]
            if s == 0 or not np.isfinite(s):
                continue
            st_ = i + 2
            en = min(st_ + 1, arr.shape[0])
            if st_ < arr.shape[0]:
                out[st_:en, j] = s
            flat = en
    pos = pd.DataFrame(out, index=sig.index, columns=sig.columns)
    inv = (1.0 / vol).where(pos != 0)
    w = inv.div(inv.abs().sum(axis=1).replace(0, np.nan), axis=0).fillna(0)
    contrib = (pos * ret * w).where(pos != 0).sum(axis=0).sort_values(ascending=False)
    print("%-24s %12s" % ("market", "contribution"))
    for m, v in contrib.items():
        print("  %-24s %+12.4f" % (m[:24], v))
    pos_n = int((contrib > 0).sum())
    print(f"\n  positive contributors: {pos_n}/{len(contrib)}")

    report["core"] = {
        "cost_sensitivity": cost_rows,
        "subperiods": per,
        "is": ist, "oos": ost,
        "contributions": {k: float(v) for k, v in contrib.items()},
    }
    out = OUT_DIR / "exp11_tradable_report.json"
    out.write_text(json.dumps(report, indent=2))
    print(f"\nWrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
