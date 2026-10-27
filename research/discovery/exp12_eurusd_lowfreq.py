"""Exp12: EURUSD low-frequency trend / breakout — PREREGISTERED before any result.

WHY THIS IS STRUCTURED DIFFERENTLY
----------------------------------
Every prior experiment in this repo selected its configuration AFTER seeing
results, which is exactly why the Day 17 audit could not establish whether
the reported edge was real. This one inverts the order: the Hypotheses,
parameters, split, cost and pass criteria are written down here first, and
`main()` only prints whatever the frozen design produces. Nothing here is
tuned.

FROZEN DESIGN (do not edit after running)
-----------------------------------------
Universe      EURUSD daily, single instrument
Data          artifacts/histdata_v9/derived/eurusd_2000-2026_d1.parquet
              <- EURUSD M1 (rebuilt from data/real/histdata)
Sample        2000-05-30 .. 2026-10-02 (8126 daily bars)

IS            2000-05-30 .. 2015-12-31
OOS           2016-01-01 .. 2026-10-02
              Same 2016 boundary used by reversal_v1, so results are
              comparable to earlier work.

Cost          1.0 pip round trip, charged ONLY on position changes
              (= the account's real terms; see cost_break_even.md)

Execution     signal computed at close of day t, position held from t+1.
              No intraday path assumption, no look-ahead.

HYPOTHESES (all four parameters are literature-standard, NOT searched)
----------------------------------------------------------------------
  donchian_20    break of trailing 20-day high/low
  donchian_55    trailing 55-day  -- classic Turtle system
  donchian_120   trailing 120-day -- long-horizon breakout
  ma_20_50       moving-average crossover, 20 vs 50
  atr_2.0        break of SMA20 +/- 2 x ATR(20)

MULTIPLE-TESTING CORRECTION
---------------------------
5 strategies tested on the same IS window -> Bonferroni family-wise alpha
0.05 => per-test alpha 0.01 => two-sided critical |t| = 2.576.

IS PASS RULE (declared now, before seeing output)
    |t_NW| > 2.576   AND   Sharpe > 0.30

OOS RULE
    Only strategies that pass IS are run on OOS.
    OOS passes if |t_NW| > 1.96 AND its Sharpe has the same sign as IS.
    If nothing passes IS, nothing is reported as an edge, full stop.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

DATA = Path("artifacts/histdata_v9/derived/eurusd_2000-2026_d1.parquet")
OUT = Path("artifacts/research/eurusd_lowfreq")

IS_END = "2015-12-31"
OOS_START = "2016-01-01"

COST_PIPS = 1.0          # account real round-trip cost
PIP = 1e-4               # EURUSD: 1 pip = 0.0001

TRADING_DAYS = 252

# Bonferroni: alpha_fam 0.05 over 5 tests -> per-test 0.01 -> two-sided
IS_T_CRIT = 2.576
IS_SHARPE_MIN = 0.30
OOS_T_CRIT = 1.96

STRATEGIES = {
    "donchian_20":  {"kind": "donchian", "n": 20},
    "donchian_55":  {"kind": "donchian", "n": 55},
    "donchian_120": {"kind": "donchian", "n": 120},
    "ma_20_50":     {"kind": "ma_cross", "fast": 20, "slow": 50},
    "atr_2.0":      {"kind": "atr", "n": 20, "k": 2.0},
}


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


def load() -> pd.DataFrame:
    df = pd.read_parquet(DATA)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    return df


def raw_signal(df: pd.DataFrame, cfg: dict) -> pd.Series:
    """Desired position as of each day's CLOSE (executed the next day)."""
    kind = cfg["kind"]
    close = df["close"]

    if kind == "donchian":
        n = cfg["n"]
        hi = df["high"].rolling(n).max()
        lo = df["low"].rolling(n).min()
        # breakout biases the state; stays flat-out until the opposite break
        sig = pd.Series(0.0, index=df.index)
        state = 0.0
        for i in range(len(df)):
            if np.isnan(hi.iloc[i]) or np.isnan(lo.iloc[i]):
                sig.iloc[i] = 0.0
                continue
            c = close.iloc[i]
            if c >= hi.iloc[i]:
                state = 1.0
            elif c <= lo.iloc[i]:
                state = -1.0
            sig.iloc[i] = state
        return sig

    if kind == "ma_cross":
        fast = close.rolling(cfg["fast"]).mean()
        slow = close.rolling(cfg["slow"]).mean()
        return np.sign(fast - slow)

    if kind == "atr":
        n, k = cfg["n"], cfg["k"]
        prev = close.shift(1)
        tr = pd.concat(
            [
                df["high"] - df["low"],
                (df["high"] - prev).abs(),
                (df["low"] - prev).abs(),
            ],
            axis=1,
        ).max(axis=1)
        atr = tr.rolling(n).mean()
        mid = close.rolling(n).mean()
        sig = pd.Series(0.0, index=df.index)
        state = 0.0
        for i in range(len(df)):
            if np.isnan(atr.iloc[i]) or np.isnan(mid.iloc[i]):
                sig.iloc[i] = 0.0
                continue
            c = close.iloc[i]
            if c >= mid.iloc[i] + k * atr.iloc[i]:
                state = 1.0
            elif c <= mid.iloc[i] - k * atr.iloc[i]:
                state = -1.0
            sig.iloc[i] = state
        return sig

    raise ValueError(kind)


def backtest(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Daily net pip P&L. Position taken at t+1 from signal at t."""
    sig = raw_signal(df, cfg)
    pos = sig.shift(1).fillna(0.0)

    ret_pips = df["close"].diff() * 1e4          # pip per day
    gross = pos * ret_pips

    turnover = pos.diff().abs().fillna(pos.abs())
    cost = turnover * COST_PIPS

    net = gross - cost
    out = pd.DataFrame(
        {"pos": pos, "gross": gross, "cost": cost, "net": net}
    ).dropna()
    return out


def summarise(net: pd.Series) -> dict:
    net = net.dropna()
    n = len(net)
    if n < 60:
        return {}
    mu, sd = net.mean(), net.std(ddof=1)
    sharpe = float(mu / sd * np.sqrt(TRADING_DAYS)) if sd > 0 else np.nan
    # overlapping daily positions -> HAC with a modest lag
    t_nw = newey_west_t(net.to_numpy(), lag=10)
    return {
        "days": n,
        "years": round(n / TRADING_DAYS, 2),
        "mean_daily_pips": round(float(mu), 5),
        "ann_sharpe": round(float(sharpe), 3),
        "t_nw": round(float(t_nw), 3),
        "total_net_pips": round(float(net.sum()), 1),
        "gross_pips": None,
        "ann_return_pips": round(float(mu) * TRADING_DAYS, 1),
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    df = load()
    print(f"data: {len(df)} daily bars  {df.index.min().date()} -> {df.index.max().date()}")
    print(f"IS  <= {IS_END}   OOS >= {OOS_START}")
    print(f"cost {COST_PIPS} pip round trip, charged on position changes only")
    print()
    print("=== IS results (pre-registered pass: |t_NW| > %.3f AND Sharpe > %.2f) ==="
          % (IS_T_CRIT, IS_SHARPE_MIN))
    print("%-14s %6s %9s %8s %11s %9s" % ("strategy", "years", "Sharpe", "t_NW", "ann_pips", "verdict"))
    print("-" * 62)

    results = {}
    is_pass = []
    for name, cfg in STRATEGIES.items():
        bt = backtest(df, cfg)
        bt_is = bt.loc[:IS_END]
        s = summarise(bt_is["net"])
        g = bt_is["gross"]
        if not s:
            print("%-14s %6s" % (name, "n/a"))
            continue
        s["gross_pips"] = round(float(g.sum()), 1)
        ok = abs(s["t_nw"]) > IS_T_CRIT and s["ann_sharpe"] > IS_SHARPE_MIN
        verdict = "PASS" if ok else "fail"
        if ok:
            is_pass.append(name)
        s["is_pass"] = ok
        print("%-14s %6.1f %9.3f %8.2f %11.1f %9s"
              % (name, s["years"], s["ann_sharpe"], s["t_nw"], s["ann_return_pips"], verdict))
        results[name] = {"cfg": cfg, "is": s}

    print()
    if not is_pass:
        print("=== NO strategy passes IS. Nothing proceeds to OOS. ===")
        oos_payload = {}
    else:
        print("=== OOS for IS passers (|t_NW| > %.2f AND same sign as IS) ===" % OOS_T_CRIT)
        print("%-14s %9s %8s %9s %8s" % ("strategy", "IS_Sharpe", "OOS_Sharpe", "OOS_t", "verdict"))
        print("-" * 56)
        oos_payload = {}
        for name in is_pass:
            bt = backtest(df, STRATEGIES[name])
            o = summarise(bt.loc[OOS_START:]["net"])
            if not o:
                print("%-14s %9s" % (name, "n/a"))
                continue
            same = np.sign(o["ann_sharpe"]) == np.sign(results[name]["is"]["ann_sharpe"])
            ok = abs(o["t_nw"]) > OOS_T_CRIT and same
            print("%-14s %9.3f %9.3f %8.2f %8s"
                  % (name, results[name]["is"]["ann_sharpe"], o["ann_sharpe"],
                     o["t_nw"], "OOS PASS" if ok else "OOS fail"))
            o["oos_pass"] = ok
            results[name]["oos"] = o
            oos_payload[name] = o

    payload = {
        "experiment": "exp12_eurusd_lowfreq_preregistered",
        "design_frozen_before_results": True,
        "data": str(DATA),
        "bars": int(len(df)),
        "range": [str(df.index.min()), str(df.index.max())],
        "is_window": ["2000-05-30", IS_END],
        "oos_window": [OOS_START, "2026-10-02"],
        "cost_pips": COST_PIPS,
        "cost_basis": "account real round trip; charged on position change only",
        "strategies": STRATEGIES,
        "multiple_testing": {
            "method": "Bonferroni, family alpha 0.05 over %d tests" % len(STRATEGIES),
            "per_test_alpha": 0.05 / len(STRATEGIES),
            "is_t_crit": IS_T_CRIT,
            "is_sharpe_min": IS_SHARPE_MIN,
            "oos_t_crit": OOS_T_CRIT,
        },
        "results": results,
    }

    out = OUT / "exp12_report.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    print()
    print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
