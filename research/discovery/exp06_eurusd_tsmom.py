#!/usr/bin/env python3
"""Exp06 -- EURUSD Time-Series Momentum (trend following) on D1.

Why this experiment is structurally different
---------------------------------------------
Exp01-03 (Reversal V1), Exp04 and Exp05 all measured the SAME mechanism:
an EVENT fires (a deviation, a breakout), then we ask where price goes.
Those are discrete, frequent, and therefore cost-dominated:

    M5 reversal : gross 0.37 pips vs 1.5 pips round trip -> cost is 400% of gross

Time-series momentum is not an event study. There is no trigger to fire:
the position simply stays on while the trend state persists and flips when
it does not. Position changes are rare (a few per year), so the cost
structure is qualitatively different:

    D1 TSMOM : gross ~100-200 pips per year of exposure, ~9 pips/yr of
               round-trip cost -> cost is a few percent of gross

That is why it is tested here: it is the only common EURUSD strategy family
whose cost ratio is not structurally broken. It is also the most robust
documented anomaly in the FX literature (Moskowitz, Ooi & Pedersen 2012,
"Time Series Momentum").

This is still a DIRECTIONALITY test, not a finished strategy: no stops, no
volatility targeting, no position sizing beyond fixed +1/-1 units, no
slippage model, no session logic.

Signal (pre-registered, NOT scanned)
------------------------------------
    signal[i] = sign( close[i] - close[i-L] )

L = 252 trading days (12 months), the standard TSMOM lookback. A second
value, L = 63 (3 months), is run ONLY as a stability check. Both values are
declared before the run; neither the choice nor the verdict is adjusted
after seeing the result, and no grid over L is searched. If the two
lookbacks disagree in sign, the effect is reported as unstable rather than
picking the better one.

Execution timing (no look-ahead)
--------------------------------
    close[i]       -> signal[i] is decided
    open[i+1]      -> position flips to signal[i]
Therefore, during bar i:
    overnight leg  close[i-1] -> open[i]   holds signal[i-2]
    intraday  leg  open[i]    -> close[i]  holds signal[i-1]
Nothing in the position at time t uses any price known only after t.

Costs
-----
    spread : 0.75 pip charged per position CHANGE (so a full flip, which is
             close + open, costs 1.5 pips round trip; opening from flat
             costs 0.75). Same 1.5 pip round-trip assumption as Exp01-05.
    swap   : charged per night the position is held, swept over
             {0, 0.3, 0.5, 1.0} pip/night because the real carry depends on
             the account and on the rate differential at the time. It is
             reported, not assumed away. Trend following holds positions for
             weeks, so this is a first-order cost, not a detail.

Verdict rules (fixed before the run)
------------------------------------
    WORTH CONTINUING : net Sharpe >= 0.5, IS and OOS same sign, and more
                       than half the calendar years positive
    INSUFFICIENT     : fewer than 15 years of usable data
    NOT ESTABLISHED  : otherwise

Reuses, modifies nothing
------------------------
Reads the existing D1 derivative parquet. Nothing in Reversal V1,
exp01-05 or the raw data is touched.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
DEFAULT_D1 = REPO / "artifacts/histdata_v9/derived/eurusd_2000-2026_d1.parquet"
DEFAULT_OUT = REPO / "artifacts/research/eurusd_tsmom"

PIP = 0.0001
LOOKBACKS = (252, 63)          # 12 months (primary), 3 months (stability)
COST_PIPS_CHANGE = 0.75        # per position change -> 1.5 round trip on a flip
SWAP_SWEEP = (0.0, 0.3, 0.5, 1.0)
OOS_YEAR = 2016                # same split as exp01-05
MIN_BARS_PER_DAY = 300         # drop incomplete trading days (holidays, data edges)
MIN_YEARS = 15                 # below this the verdict is INSUFFICIENT
SHARPE_GATE = 0.5
N_BOOT = 2000
SEED = 20240416
W = 126


def load_d1(path: Path, min_bars: int):
    """D1 bars indexed by date, with incomplete days dropped and counted."""
    df = pd.read_parquet(path)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    n_all = len(df)
    bars = df["bars"].to_numpy(float)
    sparse = bars < min_bars
    kept = df[~sparse].copy()
    ledger = {
        "bars_total": int(n_all),
        "bars_dropped_incomplete": int(sparse.sum()),
        "bars_kept": int(len(kept)),
        "min_bars_per_day": int(min_bars),
        "bars_per_day_median": round(float(np.median(bars)), 1),
        "bars_per_day_p10": round(float(np.percentile(bars, 10)), 1),
        "range": [str(kept.index.min().date()), str(kept.index.max().date())],
        "years": round((kept.index.max() - kept.index.min()).days / 365.25, 2),
    }
    return kept, ledger


def tsmom(df: pd.DataFrame, lookback: int) -> pd.DataFrame:
    """Daily position, gross/net pips and cost components. No look-ahead."""
    close = df["close"].to_numpy(float)
    open_ = df["open"].to_numpy(float)
    n = len(df)

    sig = np.zeros(n, dtype=np.int8)
    diff = np.full(n, np.nan)
    diff[lookback:] = close[lookback:] - close[:-lookback] if lookback else np.nan
    valid = np.isfinite(diff)
    sig[valid & (diff > 0)] = 1
    sig[valid & (diff < 0)] = -1

    # position held during each leg of bar i (see module docstring)
    pos_over = np.zeros(n, dtype=np.int8)   # close[i-1] -> open[i]
    pos_intra = np.zeros(n, dtype=np.int8)  # open[i]  -> close[i]
    pos_over[2:] = sig[:-2]
    pos_intra[1:] = sig[:-1]

    prev_close = np.full(n, np.nan)
    prev_close[1:] = close[:-1]

    r_gap = pos_over * (open_ - prev_close) / PIP
    r_intra = pos_intra * (close - open_) / PIP
    r_gross = r_gap + r_intra

    change = np.abs(pos_intra.astype(int) - pos_over.astype(int))
    cost_spread = COST_PIPS_CHANGE * change
    held_overnight = np.abs(pos_over.astype(int))

    # bars usable for evaluation: warm-up done, no NaN legs
    ok = valid & np.isfinite(r_gross) & np.isfinite(prev_close)
    # a bar only counts once the signal has warmed up on BOTH legs
    ok[: lookback + 2] = False

    out = pd.DataFrame({
        "signal": sig,
        "pos_overnight": pos_over,
        "pos_intraday": pos_intra,
        "r_gap": r_gap,
        "r_intra": r_intra,
        "r_gross": r_gross,
        "cost_spread": cost_spread,
        "held_overnight": held_overnight,
        "usable": ok,
    }, index=df.index)
    return out


def summarize(bt: pd.DataFrame, swap_per_night: float) -> dict:
    """Performance statistics net of spread and the given swap rate."""
    s = bt[bt["usable"]]
    if len(s) == 0:
        return {"n_days": 0}
    r_gross = s["r_gross"].to_numpy(float)
    cost_spread = s["cost_spread"].to_numpy(float)
    cost_swap = swap_per_night * s["held_overnight"].to_numpy(float)
    r_net = r_gross - cost_spread - cost_swap

    nyears = (s.index.max() - s.index.min()).days / 365.25
    trades = int((s["pos_intraday"].astype(int)
                  != s["pos_overnight"].astype(int)).sum())
    exposure = float((s["pos_intraday"] != 0).mean())
    sd = float(r_net.std(ddof=1))
    mean = float(r_net.mean())
    sharpe = mean / sd * np.sqrt(252) if sd > 0 else None

    eq = np.cumsum(r_net)
    peak = np.maximum.accumulate(eq)
    dd = eq - peak
    maxdd = float(dd.min()) if len(dd) else None

    yearly = pd.Series(r_net, index=s.index).groupby(s.index.year)
    yr = pd.DataFrame({"n": yearly.size(), "pips": yearly.sum()})
    return {
        "n_days": int(len(s)),
        "years": round(nyears, 2),
        "trades": trades,
        "trades_per_year": round(trades / nyears, 1) if nyears else None,
        "exposure_share": round(exposure, 4),
        "gross_pips_total": round(float(r_gross.sum()), 1),
        "spread_pips_total": round(float(cost_spread.sum()), 1),
        "swap_pips_total": round(float(cost_swap.sum()), 1),
        "net_pips_total": round(float(r_net.sum()), 1),
        "net_pips_per_year": round(float(r_net.sum()) / nyears, 1) if nyears else None,
        "mean_daily_pips": round(mean, 5),
        "sd_daily_pips": round(sd, 4),
        "sharpe_ann": round(sharpe, 3) if sharpe is not None else None,
        "max_drawdown_pips": round(maxdd, 1) if maxdd is not None else None,
        "win_days": round(float((r_net > 0).mean()), 4),
        "cost_share_of_gross": (round(float((cost_spread.sum() + cost_swap.sum())
                                           / abs(r_gross.sum())), 4)
                                if r_gross.sum() != 0 else None),
        "yearly": {int(y): {"n": int(row["n"]), "pips": round(float(row["pips"]), 1)}
                   for y, row in yr.iterrows()},
        "years_positive": int((yr["pips"] > 0).sum()),
        "years_counted": int(len(yr)),
        "_r_net": r_net,
        "_index": s.index,
    }


def year_block_bootstrap(r_net: np.ndarray, index, n_boot=N_BOOT, seed=SEED):
    """Year-block bootstrap of the annualised mean: daily returns are serially
    correlated and positions persist for weeks, so iid resampling of days
    would badly understate the uncertainty."""
    s = pd.Series(r_net, index=index)
    g = s.groupby(s.index.year)
    sums = g.sum().to_numpy(float)
    cnts = g.size().to_numpy(float)
    nb = len(sums)
    if nb < 3:
        return None
    rng = np.random.default_rng(seed)
    means = np.empty(n_boot)
    for b in range(n_boot):
        p = rng.integers(0, nb, nb)
        means[b] = sums[p].sum() / cnts[p].sum()
    lo, hi = np.percentile(means, [2.5, 97.5])
    return {"n_year_blocks": int(nb), "n_boot": int(n_boot), "seed": int(seed),
            "mean_daily_ci95": [round(float(lo), 5), round(float(hi), 5)],
            "ann_pips_ci95": [round(float(lo) * 252, 1), round(float(hi) * 252, 1)]}


def split_stats(bt: pd.DataFrame, swap: float, oos_year: int) -> dict:
    s = bt[bt["usable"]]
    out = {}
    for name, sel in (("IS", s.index.year < oos_year),
                      ("OOS", s.index.year >= oos_year)):
        sub = s[sel]
        if len(sub) < 30:
            out[name] = {"n_days": int(len(sub))}
            continue
        r_net = (sub["r_gross"].to_numpy(float)
                 - sub["cost_spread"].to_numpy(float)
                 - swap * sub["held_overnight"].to_numpy(float))
        ny = (sub.index.max() - sub.index.min()).days / 365.25
        sd = float(r_net.std(ddof=1))
        out[name] = {
            "n_days": int(len(sub)),
            "years": round(ny, 2),
            "net_pips_total": round(float(r_net.sum()), 1),
            "net_pips_per_year": round(float(r_net.sum()) / ny, 1) if ny else None,
            "sharpe_ann": round(float(r_net.mean()) / sd * np.sqrt(252), 3) if sd > 0 else None,
        }
    return out


def verdict(main: dict, phases: dict, min_years: int) -> dict:
    """The pre-registered rule. Nothing here is chosen after the fact."""
    if main.get("years", 0) < min_years:
        return {"verdict": "证据不足 / INSUFFICIENT EVIDENCE",
                "reason": ["only " + str(main.get("years")) + " years of usable data"]}
    sh = main.get("sharpe_ann")
    is_ = (phases.get("IS") or {}).get("net_pips_per_year")
    oos = (phases.get("OOS") or {}).get("net_pips_per_year")
    same_sign = (is_ is not None and oos is not None and np.sign(is_) == np.sign(oos))
    pos_years = main.get("years_positive", 0) > main.get("years_counted", 1) / 2
    passes = [bool(sh is not None and sh >= SHARPE_GATE), bool(same_sign), bool(pos_years)]
    reason = []
    if not passes[0]:
        reason.append("net Sharpe " + str(sh) + " < " + str(SHARPE_GATE))
    if not passes[1]:
        reason.append("IS/OOS opposite sign (IS " + str(is_) + ", OOS " + str(oos) + ")")
    if not passes[2]:
        reason.append("positive years " + str(main.get("years_positive"))
                      + "/" + str(main.get("years_counted")))
    return {"verdict": ("值得继续 / WORTH CONTINUING" if all(passes)
                        else "暂不成立 / NOT ESTABLISHED"),
            "reason": reason or ["all three gates pass"],
            "sharpe_gate": SHARPE_GATE, "sharpe": sh,
            "is_oos_same_sign": bool(same_sign),
            "majority_years_positive": bool(pos_years)}


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Exp06 EURUSD time-series momentum (D1)")
    ap.add_argument("--d1", default=str(DEFAULT_D1))
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT))
    ap.add_argument("--min-bars-per-day", type=int, default=MIN_BARS_PER_DAY)
    ap.add_argument("--cost-pips", type=float, default=COST_PIPS_CHANGE)
    ap.add_argument("--oos-year", type=int, default=OOS_YEAR)
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * W)
    print("Exp06 - EURUSD Time-Series Momentum (D1) - DIRECTIONALITY TEST")
    print("=" * W)

    df, led = load_d1(Path(args.d1), args.min_bars_per_day)
    print("data      : " + format(led["bars_kept"], ",") + " D1 bars kept of "
          + format(led["bars_total"], ",") + " (" + str(led["bars_dropped_incomplete"])
          + " incomplete days dropped, < " + str(led["min_bars_per_day"]) + " M1)")
    print("range     : " + led["range"][0] + " .. " + led["range"][1]
          + "  (" + str(led["years"]) + " years)")
    print("M1/day    : median " + str(led["bars_per_day_median"])
          + ", p10 " + str(led["bars_per_day_p10"]))
    print("signal    : sign(close[i] - close[i-L]), L in " + str(LOOKBACKS)
          + " (252 = 12m primary, 63 = 3m stability). NOT scanned.")
    print("timing    : decided on close[i], position flips at open[i+1];")
    print("            bar i holds sig[i-2] overnight and sig[i-1] intraday")
    print("cost      : " + str(args.cost_pips) + " pip per position change "
          + "(= " + str(args.cost_pips * 2) + " per full flip)")
    print("swap      : swept over " + str(SWAP_SWEEP) + " pip/night (reported)")
    print("IS/OOS    : IS year < " + str(args.oos_year) + " (same as exp01-05)")
    print("verdict   : net Sharpe >= " + str(SHARPE_GATE)
          + ", IS/OOS same sign, majority years positive")

    results = {}
    daily_frames = []

    for L in LOOKBACKS:
        bt = tsmom(df, L)
        tag = "L" + str(L)
        base = summarize(bt, 0.0)
        print("-" * W)
        print("[A] " + tag + "  (" + str(L) + " bars = "
              + ("12 months" if L == 252 else "3 months") + ")")
        if base.get("n_days", 0) == 0:
            print("    no usable days")
            results[tag] = {"error": "no usable days"}
            continue
        print("    days " + format(base["n_days"], ",") + " | years "
              + str(base["years"]) + " | trades " + format(base["trades"], ",")
              + " (" + str(base["trades_per_year"]) + "/yr) | exposure "
              + format(base["exposure_share"], ".1%"))
        print("    GROSS " + format(base["gross_pips_total"], "+.1f") + "p"
              + " | spread " + format(-base["spread_pips_total"], "+.1f") + "p")

        print("    " + format("swap/night", "<12") + format("net pips", ">12")
              + format("pips/yr", ">11") + format("Sharpe", ">9")
              + format("maxDD p", ">10") + format("cost/gross", ">12"))
        sweep = {}
        for sw in SWAP_SWEEP:
            st = summarize(bt, sw)
            sweep[str(sw)] = {k: st[k] for k in
                              ("net_pips_total", "net_pips_per_year",
                               "sharpe_ann", "max_drawdown_pips",
                               "cost_share_of_gross")}
            print("    " + format(str(sw), "<12")
                  + format(st["net_pips_total"], ">+12.1f")
                  + format(st["net_pips_per_year"], ">+11.1f")
                  + format(st["sharpe_ann"], ">9.3f")
                  + format(st["max_drawdown_pips"], ">+10.1f")
                  + format(st["cost_share_of_gross"], ">12.2%"))

        main_st = summarize(bt, 0.5)   # decision basis: 0.5 pip/night
        phases = split_stats(bt, 0.5, args.oos_year)
        boot = year_block_bootstrap(main_st["_r_net"], main_st["_index"])
        v = verdict(main_st, phases, MIN_YEARS)

        print("    IS/OOS    " + format("phase", "<6") + format("years", ">7")
              + format("net pips/yr", ">14") + format("Sharpe", ">9"))
        for ph in ("IS", "OOS"):
            p = phases.get(ph, {})
            if not p.get("n_days"):
                continue
            print("              " + format(ph, "<6")
                  + format(p.get("years"), ">7")
                  + format(p.get("net_pips_per_year"), ">+14.1f")
                  + format(p.get("sharpe_ann"), ">9.3f"))
        if boot:
            ci = boot["ann_pips_ci95"]
            print("    year-block bootstrap of annual pips CI95: ["
                  + format(ci[0], "+.1f") + ", " + format(ci[1], "+.1f")
                  + "]  (" + str(boot["n_year_blocks"]) + " blocks, contains0="
                  + str(ci[0] < 0 < ci[1]) + ")")
        print("    VERDICT   " + v["verdict"])
        for r_ in v["reason"]:
            print("              -> " + r_)

        yearly = main_st["yearly"]
        print("    years positive " + str(main_st["years_positive"]) + "/"
              + str(main_st["years_counted"]))
        good = sorted(((y, d["pips"]) for y, d in yearly.items()),
                      key=lambda t: -t[1])[:4]
        bad = sorted(((y, d["pips"]) for y, d in yearly.items()),
                     key=lambda t: t[1])[:4]
        print("    best years  : " + ", ".join(str(y) + " " + format(p, "+.0f")
                                                 for y, p in good))
        print("    worst years : " + ", ".join(str(y) + " " + format(p, "+.0f")
                                                 for y, p in bad))

        results[tag] = {
            "lookback_bars": L,
            "base_no_swap": {k: v2 for k, v2 in base.items()
                             if not k.startswith("_")},
            "swap_sweep": sweep,
            "decision_basis_swap_0_5": {k: v2 for k, v2 in main_st.items()
                                        if not k.startswith("_")},
            "is_oos": phases,
            "bootstrap": boot,
            "verdict": v,
        }
        d = bt.copy()
        d.insert(0, "lookback", L)
        daily_frames.append(d.reset_index())

    # ---------------- summary ----------------
    print("=" * W)
    print("[B] SUMMARY (decision basis: 0.5 pip/night swap, "
          + str(args.cost_pips) + "p per change)")
    print("  " + format("lookback", "<10") + format("Sharpe", ">9")
          + format("pips/yr", ">10") + format("IS pips/yr", ">13")
          + format("OOS pips/yr", ">14") + format("years+", ">8")
          + "  verdict")
    for L in LOOKBACKS:
        r_ = results.get("L" + str(L), {})
        if not r_ or "decision_basis_swap_0_5" not in r_:
            continue
        m = r_["decision_basis_swap_0_5"]
        ph = r_["is_oos"]
        isv = (ph.get("IS") or {}).get("net_pips_per_year")
        oosv = (ph.get("OOS") or {}).get("net_pips_per_year")
        print("  " + format("L=" + str(L), "<10")
              + format(m["sharpe_ann"], ">9.3f")
              + format(m["net_pips_per_year"], ">+10.1f")
              + format(isv, ">+13.1f") + format(oosv, ">+14.1f")
              + format(str(m["years_positive"]) + "/" + str(m["years_counted"]), ">8")
              + "  " + r_["verdict"]["verdict"])

    print("=" * W)
    print("[C] SCOPE")
    print("  * Directionality test: fixed +1/-1 units, no stops, no vol targeting,")
    print("    no session logic, no slippage model beyond the spread assumption.")
    print("  * Trend following needs PERSISTENCE, so the verdict is about whether")
    print("    the drift survives cost - not about whether a finished strategy exists.")
    print("  * Single-pair trend following has a low Sharpe ceiling by construction;")
    print("    a Sharpe near the gate is a signal to combine pairs, not to lever up.")
    print("  * swap is swept, not assumed: long EURUSD carry is usually negative,")
    print("    which is precisely why the sweep matters more here than in Exp04/05.")

    # ---------------- artifacts ----------------
    csv_path = out_dir / "exp06_daily.csv"
    if daily_frames:
        pd.concat(daily_frames, ignore_index=True).to_csv(csv_path, index=False)
    else:
        csv_path.write_text("")

    report = {
        "experiment": "exp06_eurusd_tsmom",
        "type": "directionality test (time-series momentum), not a finished strategy",
        "rationale": "Exp01-05 measured event-triggered direction prediction, where "
                     "cost dominates because signals are frequent and small. Trend "
                     "following is persistent exposure with rare position changes, so "
                     "its cost ratio is qualitatively different.",
        "data": led,
        "method": {
            "signal": "sign(close[i] - close[i-L])",
            "lookbacks_preregistered": list(LOOKBACKS),
            "primary_lookback": 252,
            "execution": "decided on close[i], flips at open[i+1]; bar i holds "
                         "sig[i-2] overnight and sig[i-1] intraday",
            "lookahead": "none",
            "cost_pips_per_position_change": args.cost_pips,
            "round_trip_on_flip_pips": args.cost_pips * 2,
            "swap_per_night_sweep": list(SWAP_SWEEP),
            "decision_basis_swap": 0.5,
            "is_oos": "IS year < " + str(args.oos_year) + " (same as exp01-05)",
            "uncertainty": "year-block bootstrap (daily returns are serially "
                           "correlated and positions persist for weeks)",
            "verdict_rule": {
                "WORTH CONTINUING": "net Sharpe >= " + str(SHARPE_GATE)
                                    + " AND IS/OOS same sign AND majority of "
                                      "years positive",
                "INSUFFICIENT EVIDENCE": "fewer than " + str(MIN_YEARS)
                                         + " years usable",
                "NOT ESTABLISHED": "otherwise",
            },
            "not_scanned": ["lookback is fixed at the two pre-declared values",
                            "no stop/target/vol-target parameters exist"],
        },
        "results": results,
        "caveats": [
            "Fixed +1/-1 units; no position sizing, stops or vol targeting.",
            "Spread is assumed, not measured; swap is swept, not assumed.",
            "Single-pair trend following has a low Sharpe ceiling by construction.",
            "Passing the gate means the drift survives cost, not that a deployable "
            "strategy exists.",
        ],
    }
    rp = out_dir / "exp06_report.json"
    rp.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    print("=" * W)
    print("daily  -> " + str(csv_path))
    print("report -> " + str(rp))
    print("=" * W)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
