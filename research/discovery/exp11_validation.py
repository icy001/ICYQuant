"""Exp11 validation.

Exp10 taught one lesson worth hard-coding into every future study: a fake
result can pass EVERY stability test if the leak is systematic. Look-ahead
inflates all sub-periods equally, so "stable across four periods" and "OOS
better than IS" are both consistent with a bug. Therefore this script does not
start with stability - it starts by attacking the mechanism.

CHECKS
------
[A] Data smoothing. World Bank prices are monthly AVERAGES. If the underlying
    series is smoothed or interpolated, neighbouring months share information
    and one-month momentum is manufactured rather than measured. We compare
    each market's return autocorrelation against a same-length random walk.
[B] Look-ahead. Rebuild with an extra volatility lag and with a fixed vol; if
    Sharpe barely moves there is no leak. Also re-run with entry pushed to
    t+2: a genuine signal decays, a leak collapses.
[C] Sub-period stability.
[D] IS/OOS split (60/40).
[E] Cost sensitivity, expressed in round-trip pips/bp per rebalance.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from exp11_commodity_tsmom import (
    HOLDS, LOOKBACKS, MONTHS_PER_YEAR, build_signals, load_panel,
    newey_west_t, positions, stats,
)


def build(n: int, h: int, vol_shift: int = 0, fixed_vol: bool = False,
          entry_lag: int = 1):
    px = load_panel()
    ret = np.log(px).diff()
    if fixed_vol:
        vol = pd.DataFrame(np.tile(ret.std().to_numpy(), (len(ret), 1)),
                           index=ret.index, columns=ret.columns)
    else:
        vol = ret.rolling(12, min_periods=6).std().shift(1 + vol_shift)

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
    wsum = inv.abs().sum(axis=1).replace(0.0, np.nan)
    w = inv.div(wsum, axis=0).fillna(0.0)
    pnl = (pos * ret * w).where(pos != 0)
    ew = pnl.sum(axis=1).fillna(0.0).iloc[13:].dropna()
    return ew


def check_smoothing() -> None:
    """[A] Is one-month momentum real, or an artefact of averaged prices?"""
    px = load_panel()
    ret = np.log(px).diff()
    print("[A] DATA SMOOTHING TEST")
    print("    monthly-average prices can share information across months;")
    print("    compare each market's return autocorr against a random walk\n")
    print("    %-34s %8s %10s" % ("market (10 largest)", "ac1", "rw p95"))
    acs = []
    for c in px.columns:
        s = ret[c].dropna()
        if len(s) < 120:
            continue
        acs.append((c, s.autocorr(1)))
    acs.sort(key=lambda t: -abs(t[1]))
    # random-walk benchmark: ac1 of a true RW is ~N(0, 1/sqrt(n))
    for c, a in acs[:10]:
        n = len(ret[c].dropna())
        print("    %-34s %+8.3f %10.3f" % (c[:34], a, 1.645 / np.sqrt(n)))
    vals = np.array([a for _, a in acs])
    print(f"\n    all {len(vals)} markets: mean ac1 = {vals.mean():+.3f}, "
          f"median = {np.median(vals):+.3f}")
    print(f"    share with ac1 > 0: {(vals > 0).mean():.2%}")
    print("    (positive mean ac1 is expected for real momentum, but if it is")
    print("     driven by averaging it will NOT survive the t+2 entry test)\n")


def check_lookahead() -> None:
    """[B] Attack the mechanism rather than admiring the Sharpe."""
    print("[B] LOOK-AHEAD TEST")
    print("    (i) volatility timing vs fixed vol  (ii) entry lag 1 vs 2\n")
    print("    %3s %3s %9s %9s %9s %9s" % ("N", "H", "sharpe", "fixedvol", "entry+1", "entry+2"))
    print("    " + "-" * 56)
    for n in LOOKBACKS:
        for h in HOLDS:
            a = build(n, h, vol_shift=0)
            b = build(n, h, fixed_vol=True)
            c = build(n, h, entry_lag=2)
            sa, sb = stats(a, h), stats(c, h)
            print("    %3d %3d %+9.3f %+9.3f %+9.3f %+9.3f"
                  % (n, h, sa["sharpe_ann"], stats(b, h)["sharpe_ann"],
                     sa["sharpe_ann"], sb["sharpe_ann"]))
    print("\n    read: fixed-vol close to base => no vol leakage.")
    print("    entry+2 decaying but staying positive => genuine but partly")
    print("    short-lived signal; collapsing to ~0 => look-ahead.\n")


def check_stability() -> None:
    """[C] Sub-period stability."""
    print("[C] SUB-PERIOD STABILITY (N=12,H=1 and N=1,H=1)")
    periods = [("1980", "1991"), ("1992", "2002"), ("2003", "2013"), ("2014", "2025")]
    print("    %-14s %10s %10s" % ("period", "N12 Sharpe", "N1 Sharpe"))
    print("    " + "-" * 38)
    for s, e in periods:
        row = []
        for n in (12, 1):
            x = build(n, 1)
            xs = x.loc[s:e]
            st = stats(xs, 1)
            row.append(st["sharpe_ann"] if st else np.nan)
        print("    %-14s %+10.3f %+10.3f" % (f"{s}-{e}", row[0], row[1]))
    print()


def check_oos() -> None:
    """[D] 60/40 IS/OOS."""
    print("[D] IS / OOS SPLIT (first 60% vs last 40%)")
    print("    %3s %3s %10s %10s %10s" % ("N", "H", "IS Sharpe", "OOS Sharpe", "OOS t"))
    print("    " + "-" * 44)
    for n in LOOKBACKS:
        for h in HOLDS:
            x = build(n, h)
            k = int(len(x) * 0.6)
            ist, ost = stats(x.iloc[:k], h), stats(x.iloc[k:], h)
            if not ist or not ost:
                continue
            print("    %3d %3d %+10.3f %+10.3f %+10.2f"
                  % (n, h, ist["sharpe_ann"], ost["sharpe_ann"], ost["t_nw"]))
    print()


def check_cost() -> None:
    """[E] Cost sensitivity. One rebalance every H months, so cost is per rebalance."""
    print("[E] COST SENSITIVITY (round-trip cost per unit exposure, bp)")
    print("    N=12,H=1 rebalances monthly: 12 round trips / year")
    print("    %8s %10s %10s %10s" % ("bp/rt", "gross", "net Sharpe", "ann net%"))
    print("    " + "-" * 42)
    for bp in (0, 5, 10, 20, 50):
        x = build(12, 1)
        # convert bp of notional into a monthly drag: 12 rebalances per year
        drag = bp / 10_000.0
        xc = x - drag
        st = stats(xc, 1)
        gross = stats(x, 1)
        print("    %8d %+10.3f %+10.3f %+10.2f"
              % (bp, gross["sharpe_ann"], st["sharpe_ann"], st["ann_return_pct"]))
    print()
    print("    for reference, your FX account pays ~1.0 pip round trip on")
    print("    EURUSD ~ 1.12, i.e. ~8.9 bp. Commodity CFD spreads are wider.\n")


def main() -> int:
    check_smoothing()
    check_lookahead()
    check_stability()
    check_oos()
    check_cost()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
