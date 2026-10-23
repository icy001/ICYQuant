#!/usr/bin/env python3
"""Exp10 validation: try to break the "Sharpe 1.48" result before believing it.

The headline result in exp10 is too good to accept at face value. Known FX
momentum papers land around Sharpe 0.3-0.6, not 1.5. Three things can inflate
it, and each is tested here:

  A. OVERLAP-INDUCED AUTOCORRELATION. Positions are held H days and many are
     open at once, so consecutive daily P&L observations share the same trade.
     Annualising with sqrt(252) then UNDERSTATES true volatility and OVERSTATES
     Sharpe. Fix: Newey-West standard errors with lag = H.

  B. VOL SCALING. exp10 divides each return by its own trailing 252d vol. That
     is a real, tradable risk-parity construction ONLY if the vol forecast is
     not leaking. Verified by re-running with the vol estimate shifted an extra
     day and by using a fixed in-sample vol.

  C. REGIME / SAMPLE FRAGILITY. A 27-year result can be carried by one era.
     Fix: decade-by-decade and IS/OOS split.

  D. COSTS. exp10 is gross. Applied at the user's real cost.

If the result survives all four, it is worth acting on. If it dies on A or C,
it was never there.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "research/discovery"))
from exp10_cross_asset_d1_trend import (  # noqa: E402
    load_panel, build_signals, positions, MARKET, TRADING_DAYS,
)

# user's real terms: $5 commission per side, 1 lot => $10 round turn
# 1 pip = $10/lot on EURUSD => 1.0 pip round turn
COST_PIPS = 1.0


def newey_west_t(x: np.ndarray, lag: int) -> float:
    """t-stat of the mean with Newey-West (Bartlett kernel) standard error."""
    n = len(x)
    xm = x - x.mean()
    gamma0 = float(xm @ xm) / n
    s = gamma0
    for l in range(1, lag + 1):
        w = 1.0 - l / (lag + 1.0)
        g = float(xm[l:] @ xm[:-l]) / n
        s += 2.0 * w * g
    var_mean = max(s, 1e-18) / n
    return float(x.mean() / np.sqrt(var_mean))


def build(n: int, h: int, vol_shift: int = 0, fixed_vol: bool = False):
    """Real tradable portfolio: inverse-vol weights normalised across open positions."""
    px = load_panel()
    ret = np.log(px).diff()
    if fixed_vol:
        vol = pd.DataFrame(np.tile(ret.std().to_numpy(), (len(ret), 1)),
                           index=ret.index, columns=ret.columns)
    else:
        vol = ret.rolling(TRADING_DAYS, min_periods=60).std().shift(1 + vol_shift)
    sig = build_signals(px, n)
    pos = positions(sig, h)
    inv = (1.0 / vol).where(pos != 0)
    wsum = inv.abs().sum(axis=1).replace(0.0, np.nan)
    w = inv.div(wsum, axis=0)
    pnl = (pos * ret * w).where(pos != 0)
    ew = pnl.sum(axis=1).fillna(0.0).dropna()
    return px, pos, ew


def main() -> int:
    px, _, _ = build(20, 20)
    years = (px.index[-1] - px.index[0]).days / 365.25

    print("=" * 78)
    print("Exp10 VALIDATION - attempting to break Sharpe 1.48")
    print("=" * 78)

    # ---------------- A. autocorrelation ----------------
    print("\n[A] OVERLAP-INDUCED AUTOCORRELATION")
    print("-" * 78)
    print(f"{'N':>4}{'H':>4}{'Sharpe':>9}{'t(iid)':>9}{'t(NW)':>9}{'ac1':>8}{'verdict':>12}")
    rows = []
    for n in (20, 50, 100):
        for h in (20, 60):
            _, _, ew = build(n, h)
            x = ew.to_numpy()
            sd = x.std(ddof=1)
            shr = x.mean() / sd * np.sqrt(TRADING_DAYS)
            # Testing H0: Sharpe = 0 is the same as testing H0: mean = 0, so the
            # daily-frequency t-stat IS the Sharpe t-stat:
            #   Sharpe*sqrt(years) = mean/sd*sqrt(252)*sqrt(years)
            #                      = mean*sqrt(n_days)/sd = t_iid.
            # Therefore t_nw is directly comparable to t_iid, with NO extra
            # annualisation. (An earlier version multiplied by sqrt(252)*sqrt(y)
            # on top and produced the nonsense t=44.)
            t_iid = shr * np.sqrt(years)
            t_nw = newey_west_t(x, lag=h)
            ac1 = pd.Series(x).autocorr(1)
            keep = abs(t_nw) > 1.96
            rows.append((n, h, shr, t_iid, t_nw, ac1))
            print(f"{n:>4}{h:>4}{shr:>+9.3f}{t_iid:>+9.2f}{t_nw:>+9.2f}"
                  f"{ac1:>+8.3f}{'SURVIVES' if keep else 'DIES':>12}")
    print("\n  t(NW) uses Newey-West with lag=H, which is the honest number.")
    print("  Compare t(iid) vs t(NW): the gap is how much overlap was inflating it.")

    # ---------------- B. vol scaling leakage ----------------
    print("\n[B] VOL-SCALING LOOK-AHEAD CHECK")
    print("-" * 78)
    print(f"{'vol setup':<28}{'Sharpe':>9}{'delta':>9}")
    base_shr = None
    for label, kw in [("trailing252 shift1 (exp10)", dict()),
                      ("trailing252 shift2", dict(vol_shift=1)),
                      ("full-sample fixed vol", dict(fixed_vol=True))]:
        _, _, ew = build(20, 20, **kw)
        x = ew.to_numpy()
        shr = x.mean() / x.std(ddof=1) * np.sqrt(TRADING_DAYS)
        if base_shr is None:
            base_shr = shr
        print(f"{label:<28}{shr:>+9.3f}{shr-base_shr:>+9.3f}")
    print("  If the fixed-vol variant were much higher, exp10's vol forecast")
    print("  would be leaking. Small deltas = the vol timing is not the edge.")

    # ---------------- C. regime fragility ----------------
    print("\n[C] REGIME / SAMPLE FRAGILITY (N=20 H=20)")
    print("-" * 78)
    _, _, ew = build(20, 20)
    print(f"{'period':<14}{'days':>7}{'Sharpe':>9}{'ann%':>9}")
    for a, b in [(2000, 2007), (2008, 2013), (2014, 2019), (2020, 2026)]:
        s = ew[(ew.index.year >= a) & (ew.index.year <= b)]
        if len(s) < 60:
            continue
        x = s.to_numpy()
        shr = x.mean() / x.std(ddof=1) * np.sqrt(TRADING_DAYS)
        print(f"{f'{a}-{b}':<14}{len(s):>7}{shr:>+9.3f}{x.mean()*TRADING_DAYS*100:>+9.2f}")
    n_is = int(len(ew) * 0.6)
    for label, s in [("IS  first 60%", ew.iloc[:n_is]), ("OOS last 40%", ew.iloc[n_is:])]:
        x = s.to_numpy()
        shr = x.mean() / x.std(ddof=1) * np.sqrt(TRADING_DAYS)
        print(f"{label:<14}{len(s):>7}{shr:>+9.3f}{x.mean()*TRADING_DAYS*100:>+9.2f}")

    # ---------------- D. costs ----------------
    print("\n[D] COST SENSITIVITY (user: $5/side/lot => 1.0 pip round turn)")
    print("-" * 78)
    px2, pos, _ = build(20, 20)
    ret = np.log(px2).diff()
    # trades entered = position changes from 0 to nonzero
    ent = ((pos != 0) & (pos.shift(1) == 0)).sum(axis=1)
    yr = years
    print(f"{'cost(pips)':>11}{'trades/yr':>11}{'Sharpe':>9}{'net ann%':>10}")
    for c in (0.0, 0.15, 0.3, 0.5, 1.0):
        # a round turn costs c pips of the pair's price; in vol units use
        # approximate pip value relative to daily vol
        px_pip = 0.0001 / px2  # 1 pip as a fraction of price
        px_pip = px_pip.replace([np.inf, -np.inf], np.nan)
        cost_ret = px_pip * c
        gross = (pos * ret).where(pos != 0).mean(axis=1).fillna(0.0)
        cost = (ent * cost_ret.mean(axis=1)).fillna(0.0)
        net = gross - cost
        x = net.to_numpy()
        shr = x.mean() / x.std(ddof=1) * np.sqrt(TRADING_DAYS)
        tpy = ent.sum() / yr
        print(f"{c:>11.2f}{tpy:>11.1f}{shr:>+9.3f}{x.mean()*TRADING_DAYS*100:>+10.2f}")

    print("\n" + "=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
