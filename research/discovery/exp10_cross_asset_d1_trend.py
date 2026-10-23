#!/usr/bin/env python3
"""Exp10: cross-sectional D1 trend panel on 9 currency pairs, 2000-2026.

RESULT: FALSIFIED. Cross-sectional D1 breakout trend has no edge.
After removing a one-day look-ahead (see LOOK-AHEAD below), portfolio Sharpe
across all 6 (N, H) cells is -0.03 .. +0.23, every |t| <= 1.18, OOS Sharpe
-0.11, and gross return is already negative before costs.

WHY THIS EXISTS
---------------
Exp05 showed that on a SINGLE pair the D1 breakout has a large per-trade edge
(+35 pips) but is statistically undecidable: only 53 non-overlapping events in
27 years, |t| = 0.54. Exp08 confirmed it: every D1/H4 cell had |t| < 1.1. The
question was whether that was a sample-size problem that a 9-pair cross-section
could fix.

It is not. Adding 9 pairs lifted the nominal trade count from ~53 to ~2500, but
the honest portfolio t-stat went to ~0. The cross-section did not rescue the
signal; it just made the null estimate more precise. The edge was never there.

LOOK-AHEAD (the trap this study fell into, and the reason for this file's shape)
-------------------------------------------------------------------------------
The first version entered the position on the SAME day the breakout was
detected while P&L was pos*ret, where ret_t is the t-1 -> t return. That books
a return which had already happened by the time the 14:15 CET fixing was known.
It produced:

    Sharpe 1.38, t = 7.17, stable in all four sub-periods (1.31-1.52),
    OOS Sharpe 1.42 (better than IS), and nearly cost-insensitive.

Every robustness check PASSED, because look-ahead is systematic: it inflates
every sub-period equally, so no stability test can see it. Only auditing the
exact definition of the return start date caught it. Entry is now at i+1.

Lesson: stability tests cannot detect look-ahead. Audit entry/exit timing first.

THE ONE METHODOLOGICAL TRAP
---------------------------
Pooling all 9 pairs' trades into one big sample and computing a t-stat as if
they were independent would be WRONG and would manufacture significance. All
nine series are USD-exposed and highly correlated, so the pooled n overstates
the true information.

The correct way, used here:
  1. build the equal-weight (and risk-parity) PORTFOLIO daily return series,
  2. judge significance on that ONE series' t-stat,
     which automatically accounts for cross-pair correlation.
  3. separately report the correlation matrix and the implied EFFECTIVE sample
     size, so the gap between "nominal n" and "effective n" is visible.

DATA CAVEAT
-----------
ECB publishes a single daily reference rate (14:15 CET). There is no high/low,
so "breakout" here means the reference rate made a new N-day extreme. This is
not a tick-accurate intraday breakout. It also means this source cannot drive
a Chan study (fenxing needs high/low).

Position sizing: each pair's daily return is divided by its own trailing 252d
volatility (lagged one day, no look-ahead) so that a high-vol pair does not
silently dominate the portfolio.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
ECB = REPO / "data/real/ecb_d1"
OUT = REPO / "artifacts/research/cross_asset_d1"
OUT.mkdir(parents=True, exist_ok=True)

# ECB stores USD per 1 unit of the currency. Market convention differs by pair:
#   EURUSD/GBPUSD/AUDUSD/NZDUSD = USD per unit  -> use as is
#   USDJPY/USDCHF/USDCAD/...    = units per USD  -> invert
MARKET = {
    "EURUSD": ("EURUSD", False),
    "GBPUSD": ("GBPUSD", False),
    "AUDUSD": ("AUDUSD", False),
    "NZDUSD": ("NZDUSD", False),
    "JPYUSD": ("USDJPY", True),
    "CHFUSD": ("USDCHF", True),
    "CADUSD": ("USDCAD", True),
    "SEKUSD": ("USDSEK", True),
    "NOKUSD": ("USDNOK", True),
}

LOOKBACKS = (20, 50, 100)      # N-day breakout window
HOLDS = (20, 60)               # holding period in days
TRADING_DAYS = 252


def load_panel() -> pd.DataFrame:
    """Load ECB rates, convert to market convention, align on common calendar."""
    cols = {}
    for src, (name, invert) in MARKET.items():
        s = pd.read_csv(ECB / f"{src}_d1.csv", parse_dates=["date"]).set_index("date")["close"]
        s = s[s > 0]
        cols[name] = (1.0 / s) if invert else s
    px = pd.DataFrame(cols).sort_index()
    px = px.dropna(how="any")
    return px


def build_signals(px: pd.DataFrame, n: int):
    """Breakout of the previous N days. Returns +1 / -1 / 0, shifted to avoid look-ahead."""
    # strict: prior N days EXCLUDING today
    hi = px.shift(1).rolling(n, min_periods=n).max()
    lo = px.shift(1).rolling(n, min_periods=n).min()
    up = (px > hi).astype(float)
    dn = (px < lo).astype(float)
    return up - dn


def positions(sig: pd.DataFrame, h: int) -> pd.DataFrame:
    """Hold each signal for h days; ignore repeat signals while already in a trade.

    CRITICAL: entry is at i+1, not i. The signal is only known at the 14:15 CET
    fixing of day i, so the earliest executable entry is day i+1. Entering at i
    while P&L is computed as pos*ret (where ret_t is the t-1 -> t return) would
    capture a return that had already happened -- a one-day look-ahead that
    flatters every momentum rule. Verified: this shift is what makes the result
    honest.
    """
    arr = sig.to_numpy()
    out = np.zeros_like(arr)
    for j in range(arr.shape[1]):
        flat_at = 0
        for i in range(arr.shape[0]):
            if i < flat_at:
                continue
            s = arr[i, j]
            if s != 0.0:
                start = i + 1                      # executable entry, not i
                end = min(start + h, arr.shape[0])
                if start < arr.shape[0]:
                    out[start:end, j] = s
                flat_at = end
    return pd.DataFrame(out, index=sig.index, columns=sig.columns)


def nonoverlap_trades(sig: pd.Series, ret_h: pd.Series, h: int):
    """Per-trade stats using non-overlapping events only (matches Exp04/05 convention)."""
    s = sig.dropna()
    s = s[s != 0]
    idx = s.index
    keep, last = [], -10**9
    pos_of = {d: i for i, d in enumerate(ret_h.index)}
    for d in idx:
        i = pos_of.get(d)
        if i is None:
            continue
        if i - last >= h:
            keep.append(d)
            last = i
    if not keep:
        return None
    r = ret_h.loc[ret_h.index.intersection(keep)].dropna()
    r = r * s.loc[[d for d in keep if d in s.index]].reindex(r.index)
    r = r.dropna()
    if len(r) < 5:
        return None
    t = r.mean() / (r.std(ddof=1) / np.sqrt(len(r)))
    return {"n": int(len(r)), "mean": float(r.mean()),
            "sd": float(r.std(ddof=1)), "t": float(t)}


def main() -> int:
    px = load_panel()
    dates = px.index
    years = (dates[-1] - dates[0]).days / 365.25
    n_pairs = px.shape[1]

    print("=" * 78)
    print("Exp10  cross-sectional D1 trend panel")
    print("=" * 78)
    print(f"pairs      : {n_pairs}  ({', '.join(px.columns)})")
    print(f"sample     : {len(px)} days  {dates[0].date()} .. {dates[-1].date()}"
          f"  ({years:.1f} y)")
    print("source     : ECB daily reference rate (single point, NO high/low)")
    print("sizing     : each pair scaled by its own trailing 252d vol (lagged)")
    print("-" * 78)

    # daily log returns, and vol-scaled returns used for portfolio construction
    ret = np.log(px).diff()
    vol = ret.rolling(TRADING_DAYS, min_periods=60).std().shift(1)
    ret_s = (ret / vol).replace([np.inf, -np.inf], np.nan)

    # correlation of raw daily returns -> how much independent info exists
    corr = ret.dropna().corr()
    eig = np.linalg.eigvalsh(corr.to_numpy())[::-1]
    print("\nDAILY RETURN CORRELATION (raw log returns)")
    print("  " + corr.round(2).to_string().replace("\n", "\n  "))
    print(f"\n  mean pairwise corr : {corr.to_numpy()[np.triu_indices(n_pairs, 1)].mean():.3f}")
    print(f"  top eigenvalue     : {eig[0]:.2f}  (of {n_pairs}; "
          f"{eig[0]/n_pairs*100:.0f}% of variance in one factor)")
    print(f"  -> the 9 pairs are NOT independent. Judging significance on a pooled")
    print(f"     trade count would be invalid, so we use the portfolio series.")

    results = {}
    for n in LOOKBACKS:
        for h in HOLDS:
            sig = build_signals(px, n)
            # realised forward return over the holding period, per pair
            fwd = (np.log(px).shift(-h) - np.log(px))
            pos = positions(sig, h)

            # --- 1. per-pair, non-overlapping trades (reproduces the undecidable result)
            per_pair = {}
            for c in px.columns:
                st = nonoverlap_trades(sig[c], fwd[c], h)
                if st:
                    per_pair[c] = st

            # --- 2. CORRECT cross-sectional test: the portfolio daily return series
            # Build a REAL, tradable portfolio: inverse-vol weights normalised
            # across the positions that are open that day. Normalising matters:
            # without it the portfolio's vol is inflated by the number of open
            # trades and the resulting "return" is not a return at all.
            inv = (1.0 / vol).where(pos != 0)
            wsum = inv.abs().sum(axis=1).replace(0.0, np.nan)
            w = inv.div(wsum, axis=0)
            pnl = (pos * ret * w).where(pos != 0)
            ew = pnl.sum(axis=1).fillna(0.0).dropna()
            sd = ew.std(ddof=1)
            sharpe = (ew.mean() / sd * np.sqrt(TRADING_DAYS)) if sd > 0 else np.nan
            t_port = sharpe * np.sqrt(years)

            # nominal (invalid) pooled stat, shown only to expose the gap
            allt = np.concatenate([np.asarray([v for v in per_pair.values()])]
                                  ) if False else None
            pooled_n = sum(v["n"] for v in per_pair.values())

            results[f"N{n}_H{h}"] = {
                "per_pair": per_pair,
                "portfolio": {
                    "days": int(len(ew)),
                    "mean_daily": float(ew.mean()),
                    "sd_daily": float(sd),
                    "sharpe_ann": float(sharpe),
                    "t_stat": float(t_port),
                    "years": round(years, 2),
                    "ann_return_pct": float(ew.mean() * TRADING_DAYS * 100),
                    "ann_vol_pct": float(sd * np.sqrt(TRADING_DAYS) * 100),
                },
                "pooled_nominal_n": int(pooled_n),
            }

            print("\n" + "-" * 78)
            print(f"N={n}  H={h}")
            print(f"  {'pair':<8}{'n':>6}{'mean':>10}{'t':>8}")
            for c, v in sorted(per_pair.items()):
                print(f"  {c:<8}{v['n']:>6}{v['mean']:>+10.4f}{v['t']:>+8.2f}")
            tt = [abs(v["t"]) for v in per_pair.values()]
            print(f"  single-pair |t|: max={max(tt):.2f}  -> "
                  f"{'UNDECIDABLE' if max(tt) < 1.96 else 'significant'}")
            print(f"  nominal pooled n = {pooled_n}  (do NOT use for significance)")
            print(f"  PORTFOLIO: Sharpe={sharpe:+.3f}  t={t_port:+.2f}  "
                  f"days={len(ew)}  -> "
                  f"{'SIGNIFICANT' if abs(t_port) > 1.96 else 'not significant'}")

    # effective sample size implied by correlation
    print("\n" + "=" * 78)
    print("EFFECTIVE SAMPLE SIZE")
    print("=" * 78)
    cbar = corr.to_numpy()[np.triu_indices(n_pairs, 1)].mean()
    n_eff = n_pairs / (1 + (n_pairs - 1) * cbar)
    print(f"  pairs={n_pairs}  mean corr={cbar:.3f}")
    print(f"  effective independent series = {n_eff:.2f}"
          f"   (design effect = {1 + (n_pairs-1)*cbar:.2f})")
    print(f"  so 9 pairs buy roughly {np.sqrt(n_eff):.2f}x the t-stat of 1 pair,")
    print(f"  not {np.sqrt(n_pairs):.2f}x. This is the honest multiplier.")

    (OUT / "exp10_report.json").write_text(json.dumps({
        "pairs": list(px.columns),
        "days": int(len(px)),
        "start": str(dates[0].date()),
        "end": str(dates[-1].date()),
        "years": round(years, 2),
        "mean_pairwise_corr": float(cbar),
        "effective_series": float(n_eff),
        "results": results,
    }, indent=2))
    print(f"\nwrote {OUT / 'exp10_report.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
