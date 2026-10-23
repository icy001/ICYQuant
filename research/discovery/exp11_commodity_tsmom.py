"""Exp11: cross-sectional time-series momentum on 67 commodities, 1980-2025.

RESULT: a real but modest short-horizon commodity trend survives; the headline
number does not. See "THE SMOOTHING TRAP" before quoting any Sharpe here.

    entry at t+1 : Sharpe 3.07 (N=1,H=1), t_NW 19.0   <-- DO NOT USE
    entry at t+2 : Sharpe 0.66 (N=1,H=1), t_NW  4.36  <-- honest estimate

The t+1 figure is inflated ~5x by the data, not by a bug in the code (see
below). Classic 12-month momentum, the horizon the literature favours, is NOT
significant once the inflation is removed (t_NW 0.77).

THE SMOOTHING TRAP (the finding that matters most here)
-------------------------------------------------------
World Bank prices are monthly AVERAGES. A month-t average is not fully
determined until month t ends, and neighbouring monthly averages share
information, so the series carries strong artificial positive autocorrelation:
97% of the 67 markets have positive return autocorrelation, mean +0.245,
against a random-walk benchmark of about +/-0.07. TSP +0.49, rice +0.49,
shrimp +0.47, copper +0.34.

Pushing entry from t+1 to t+2 removes this and collapses the result:

    N=1  H=1  : 3.073 -> 0.663   (-78%)
    N=3  H=1  : 1.701 -> 0.547   (-68%)
    N=6  H=1  : 0.979 -> 0.366   (-63%)
    N=12 H=1  : 0.672 -> 0.117   (-83%)

So an entry at t+1 is still contaminated even though it looks correct on
paper. This is the second time in this project that a data-level leak
survived every stability test (Exp10 was the first, with a one-day look-ahead
in the FX panel): sub-period stability, IS/OOS and cost curves were all green
at t+1. Only asking "what happens if I trade one period later?" exposed it.

HONEST RESULT (entry at t+2)
----------------------------
    N=1  H=1 : Sharpe 0.663, t_NW 4.36, positive in all four sub-periods
               (0.43 / 0.74 / 0.92 / 0.68), OOS Sharpe 0.777 (t 3.14)
    N=3  H=1 : Sharpe 0.547, t_NW 3.61
    N=12 H=1 : Sharpe 0.117, t_NW 0.77  -- not significant

Break-even round-trip cost is about 30 bp; at 20 bp Sharpe is 0.24 and net
return 1.34%/yr, at 50 bp it is -0.40. Commodity CFD spreads are typically
wider than FX, so this thin edge may not survive real execution.

CAVEAT: these are spot/average prices, not futures, so roll yield is ignored.
For commodities in contango that is a material additional drag.

WHY THIS STUDY EXISTS
---------------------
Exp10 falsified FX trend on a 9-pair panel: after fixing a one-day look-ahead,
portfolio Sharpe was -0.03..+0.23 with every |t| <= 1.18. Two candidate
explanations remained:

    (a) trend does not exist in FX, or
    (b) the FX panel was still too small / too noisy to see it.

Commodities are the natural discriminator because trend evidence there is far
stronger in the literature (Moskowitz-Ooi-Pedersen 2012 report Sharpe around
1.0 across 58 futures markets, monthly), and the World Bank Pink Sheet gives
67 series over 66 years at no cost.

DATA
----
World Bank Pink Sheet, monthly average prices, 67 commodities.
Restricted to 1980-01 onward: before ~1975 a large share of the series are
constant or spliced (Brent equals Dubai in 100% of 1960-1970 months; gold is
fixed at USD 35/oz under Bretton Woods), which would manufacture fake
persistence. From 1980 the fraction of genuinely moving observations is >=0.88.

METHOD
------
Classic time-series momentum, monthly rebalance:

    signal_t = sign( sum of last N monthly log returns )      (known at end of t)
    hold     = month t+1                                      (entry at t+1)
    weight   = inverse ex-ante volatility, normalised across open positions

The t+1 entry is not cosmetic. Signal month t and P&L month t are the SAME
month here, so entering at t would be a one-month look-ahead of exactly the
kind that inflated Exp10 to a fake Sharpe of 1.38.

OUTPUT
------
artifacts/research/commodity_tsmom/exp11_report.json
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

DATA = Path("data/real/worldbank_commodities/commodities_monthly.csv")
OUT_DIR = Path("artifacts/research/commodity_tsmom")

START = "1980-01"          # data quality cut (see module docstring)
MONTHS_PER_YEAR = 12

LOOKBACKS = (1, 3, 6, 12)  # months used to form the signal
HOLDS = (1, 3, 6)          # months held


def load_panel() -> pd.DataFrame:
    px = pd.read_csv(DATA, index_col=0)
    px.index = pd.PeriodIndex(px.index, freq="M")
    px = px.loc[START:]
    # Require a reasonably long, mostly-continuous history in the study window.
    keep = [c for c in px.columns if px[c].notna().sum() >= 240]
    px = px[keep].copy()
    px = px.sort_index()
    return px


def newey_west_t(x: np.ndarray, lag: int) -> float:
    """t-stat of the mean with Newey-West HAC standard errors."""
    n = len(x)
    if n < 10:
        return float("nan")
    mu = x.mean()
    e = x - mu
    gamma0 = (e @ e) / n
    var = gamma0
    for L in range(1, lag + 1):
        g = (e[L:] @ e[:-L]) / n
        w = 1.0 - L / (lag + 1.0)
        var += 2.0 * w * g
    var = max(var, 1e-18)
    se = np.sqrt(var / n)
    return float(mu / se)


def build_signals(px: pd.DataFrame, n: int) -> pd.DataFrame:
    """sign of the trailing N-month return, known only at the END of month t."""
    r = np.log(px).diff()
    mom = r.rolling(n, min_periods=n).sum()
    sig = np.sign(mom)
    return sig.where(mom.abs() > 1e-12)          # drop exact-zero momentum


def positions(sig: pd.DataFrame, h: int) -> pd.DataFrame:
    """Enter at t+1 (first month after the signal is known), hold h months.

    CRITICAL: signal for month t uses month t's own average price, which is
    only complete once month t has ended. The earliest executable entry is
    month t+1. Entering at t is a one-month look-ahead.
    """
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
            start = i + 1                      # executable entry, NOT i
            end = min(start + h, nrows)
            if start < nrows:
                out[start:end, j] = s
            flat_at = end
    return pd.DataFrame(out, index=sig.index, columns=sig.columns)


def portfolio(px: pd.DataFrame, n: int, h: int):
    """Equal-risk monthly portfolio return series for one (N, H) cell."""
    ret = np.log(px).diff()
    # ex-ante vol from the trailing 12 months, shifted one month so it cannot
    # use the month being traded
    vol = ret.rolling(12, min_periods=6).std().shift(1)

    sig = build_signals(px, n)
    pos = positions(sig, h)

    inv = (1.0 / vol).where(pos != 0)
    wsum = inv.abs().sum(axis=1).replace(0.0, np.nan)
    w = inv.div(wsum, axis=0).fillna(0.0)

    pnl = (pos * ret * w).where(pos != 0)
    ew = pnl.sum(axis=1).fillna(0.0)

    ew = ew.iloc[13:].dropna()                 # drop warm-up
    return ew, pos, ret, vol


def stats(x: pd.Series, h: int) -> dict:
    x = x.dropna()
    n = len(x)
    if n < 24:
        return {}
    mu, sd = x.mean(), x.std(ddof=1)
    sharpe = (mu / sd * np.sqrt(MONTHS_PER_YEAR)) if sd > 0 else np.nan
    years = n / MONTHS_PER_YEAR
    t_iid = sharpe * np.sqrt(years)
    # HAC: overlapping holds induce MA(h-1) serial correlation
    t_nw = newey_west_t(x.to_numpy(), lag=max(h, 1))
    ac1 = x.autocorr(1)
    return {
        "months": int(n),
        "years": round(years, 2),
        "mean_monthly": float(mu),
        "sd_monthly": float(sd),
        "sharpe_ann": float(sharpe),
        "t_iid": float(t_iid),
        "t_nw": float(t_nw),
        "ac1": float(ac1) if pd.notna(ac1) else 0.0,
        "ann_return_pct": float(mu * MONTHS_PER_YEAR * 100),
        "ann_vol_pct": float(sd * np.sqrt(MONTHS_PER_YEAR) * 100),
    }


def per_market(px: pd.DataFrame, n: int, h: int) -> list[dict]:
    """Single-market results, to show what the cross-section buys us."""
    ret = np.log(px).diff()
    sig = build_signals(px, n)
    pos = positions(sig, h)
    rows = []
    for c in px.columns:
        s = (pos[c] * ret[c]).replace(0.0, np.nan).dropna()
        if len(s) < 24:
            continue
        sd = s.std(ddof=1)
        if sd <= 0:
            continue
        sh = s.mean() / sd * np.sqrt(MONTHS_PER_YEAR)
        rows.append({
            "market": c,
            "n": int(len(s)),
            "sharpe_ann": float(sh),
            "t_nw": float(newey_west_t(s.to_numpy(), lag=max(h, 1))),
        })
    return rows


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    px = load_panel()
    print(f"Panel: {px.shape[1]} commodities x {len(px)} months "
          f"({px.index[0]} .. {px.index[-1]})")
    print(f"Non-null cells: {int(px.notna().sum().sum())} / {px.size}\n")

    results: dict[str, dict] = {}
    print("  N   H   months   Sharpe     t_iid      t_NW     ac1    ann%   vol%")
    print("  " + "-" * 68)
    for n in LOOKBACKS:
        for h in HOLDS:
            ew, pos, ret, vol = portfolio(px, n, h)
            st = stats(ew, h)
            if not st:
                continue
            key = f"N{n}_H{h}"
            results[key] = st
            print(f"{n:>3}{h:>4}{st['months']:>9}{st['sharpe_ann']:>+9.3f}"
                  f"{st['t_iid']:>+10.2f}{st['t_nw']:>+9.2f}{st['ac1']:>+8.3f}"
                  f"{st['ann_return_pct']:>+8.2f}{st['ann_vol_pct']:>7.2f}")

    print("\n--- single-market comparison at N=12, H=1 (why the cross-section matters) ---")
    single = per_market(px, 12, 1)
    single.sort(key=lambda r: -r["sharpe_ann"])
    print(f"  markets tested: {len(single)}")
    print(f"  best  sharpe {single[0]['sharpe_ann']:+.3f} (t={single[0]['t_nw']:+.2f})  "
          f"{single[0]['market'][:38]}")
    print(f"  worst sharpe {single[-1]['sharpe_ann']:+.3f} (t={single[-1]['t_nw']:+.2f})  "
          f"{single[-1]['market'][:38]}")
    med = np.median([r["sharpe_ann"] for r in single])
    sig_ = [r for r in single if abs(r["t_nw"]) > 1.96]
    print(f"  median market Sharpe {med:+.3f}; individually |t|>1.96 in "
          f"{len(sig_)}/{len(single)} markets")
    top = [r for r in single if r["t_nw"] > 1.96]
    print(f"  individually significant and POSITIVE: {len(top)}/{len(single)}")

    # Effective breadth: how independent are these markets really?
    r = np.log(px).diff().iloc[13:]
    corr = r.corr()
    iu = np.triu_indices_from(corr.to_numpy(), k=1)
    cvals = corr.to_numpy()[iu]
    cvals = cvals[np.isfinite(cvals)]
    cov = r.iloc[-240:].corr().to_numpy()
    ev = np.linalg.eigvalsh(np.nan_to_num(cov))[::-1]
    ev = ev[ev > 1e-12]
    print(f"\n  mean pairwise correlation of monthly returns: {cvals.mean():+.3f}")
    print(f"  PC1 share of variance (last 20y): {ev[0]/ev.sum():.3f}")

    report = {
        "study": "exp11_commodity_tsmom",
        "source": "World Bank Pink Sheet, monthly average prices",
        "span": f"{px.index[0]} .. {px.index[-1]}",
        "n_markets": int(px.shape[1]),
        "months": int(len(px)),
        "results": results,
        "single_market_n12_h1": {
            "n_markets": len(single),
            "median_sharpe": float(med),
            "n_individually_significant": len(sig_),
            "best": single[0],
            "worst": single[-1],
        },
        "mean_pairwise_corr": float(cvals.mean()),
        "pc1_share": float(ev[0] / ev.sum()),
    }
    out = OUT_DIR / "exp11_report.json"
    out.write_text(json.dumps(report, indent=2))
    print(f"\nWrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
