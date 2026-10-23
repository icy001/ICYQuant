#!/usr/bin/env python3
"""EURUSD Reversal V1 -- Experiment 02: trigger-threshold sweep on to-O variant.

Why this experiment
-------------------
exp01 (reversal_v1_tp_window_report.json) showed the to-O + 15-18 + A combo
earned +1,006 pips net over 280 trades (OOS 40 trades, expR +0.439). But the
"revert to day open" target was hit only 2 times in 280 trades; the realized
edge came from a 24-bar time stop. So we don't yet know whether:

  (a) lowering the trigger threshold raises the O-hit rate and reveals a real
      mean-reversion mechanism, or
  (b) the edge was just 2-hour post-trigger drift, in which case lowering
      the threshold should not improve expectancy and may worsen it.

This experiment lowers the trigger threshold from 1.0% to 0.5% and 0.3%
holding every other condition frozen. If (a), the 0.3% group should show a
materially higher O-hit rate and non-negative net expectancy. If (b), the
0.3% group should fill with low-quality entries and net expectancy should
fall.

Frozen conditions
-----------------
  window   Beijing 15:00-18:00
  stop     A: fixed 20 pips
  target   revert to day open O
  cost     1.5 pips round trip (ASSUMED; data is single-sided bid)
  time     24 bars (2 hours) hard stop, plus day-end flatten

Variable
--------
  threshold pct: 0.3% / 0.5% / 1.0%
    - 1.0% is the exp01 baseline, re-run here on the same code path so
      numbers are apples-to-apples.
    - 0.3% and 0.5% are the candidates. They are TESTABLE CANDIDATES, not
      pre-validated improvements.

New vs exp01
------------
  - triggers_in_window count: bars that met |price - O| >= pct in the
    configured window regardless of position state
  - entries = signals actually opened
  - O-hit rate, stop-hit rate, time-stop rate, day-end rate
  - holding_bars per trade, plus a sub-distribution for O-hit trades
  - per-year net pips
  - cost sensitivity 0.5-3.0 pips

Data
----
artifacts/histdata_v9/parsed/eurusd_2000-2026_bars.parquet
Time: fixed EST(UTC-5) -> Beijing = ts + 13h (proven off the FX calendar
in exp01 / eurusd_m1_audit.py).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))
from eurusd_reversal_v1_m5 import (   # noqa: E402
    load_m5, build_days, PIP, USD_PER_PIP_1LOT,
    STORED_TO_BEIJING, fnum,
)

REPO = Path(__file__).resolve().parents[2]
DEFAULT_M1 = REPO / "artifacts/histdata_v9/parsed/eurusd_2000-2026_bars.parquet"
DEFAULT_OUT = REPO / "artifacts/research/eurusd_reversal_v1"

WIN_START_HR = 15
WIN_END_HR = 18
MIN_STOP_PIPS = 5.0


def simulate(days, *, pct, fixed_pips, max_hold, cost_pips,
             count_triggers: bool) -> tuple[list[dict], dict, list[int]]:
    """Forward walk. Identical control flow to exp01 simulate() with three
    additions:
      * `triggers_in_window` -- bars that met |price-O| >= pct in the
        configured window, counted whether or not a position is open.
      * `holding_bars` recorded on every trade.
      * target is always "revert to O" (this experiment is to-O only)."""
    trades: list[dict] = []
    guard = {"triggers_in_window": 0, "signals": 0,
             "boundary_stop_too_tight": 0, "closed_at_day_end": 0}
    hld: list[int] = []

    def book(d, ts_arr, pos, exit_px, reason, exit_i):
        side, entry, risk = pos["side"], pos["entry"], pos["risk"]
        gross_pips = side * (exit_px - entry) / PIP
        risk_pips = risk / PIP if risk else 0.0
        gross_r = gross_pips / risk_pips if risk_pips else 0.0
        cost_r = cost_pips / risk_pips if risk_pips else 0.0
        net_pips = gross_pips - cost_pips
        holding = int(exit_i - pos["entry_i"])
        hld.append(holding)
        trades.append({
            "date": str(d["date"]),
            "side": "long" if side == 1 else "short",
            "entry_bar": str(ts_arr[pos["entry_i"]]),
            "exit_bar": str(ts_arr[exit_i]),
            "day_open": round(pos["O"], 5),
            "target_px": round(pos["target"], 5),
            "entry_px": round(entry, 5),
            "stop_px": round(pos["stop"], 5),
            "exit_px": round(exit_px, 5),
            "distance_to_O_at_entry_pips": round(abs(pos["O"] - entry) / PIP, 1),
            "risk_pips": round(risk_pips, 2),
            "exit_reason": reason,
            "gross_pips": round(gross_pips, 2),
            "net_pips": round(net_pips, 2),
            "gross_R": round(gross_r, 4),
            "net_R": round(gross_r - cost_r, 4),
            "net_usd_1lot": round(net_pips * USD_PER_PIP_1LOT, 2),
            "holding_bars": holding,
        })

    for d in days:
        h_arr, l_arr, c_arr, ts_arr = d["h"], d["l"], d["c"], d["ts"]
        n = len(h_arr)
        O = float(d["o"][0])
        if not np.isfinite(O) or O <= 0:
            continue
        U, L = O * (1.0 + pct), O * (1.0 - pct)

        pos = None
        i = 0
        while i < n:
            if pos is None:
                hr = int(ts_arr[i].hour)
                if hr >= WIN_END_HR:
                    break
                if count_triggers and WIN_START_HR <= hr < WIN_END_HR:
                    if float(h_arr[i]) >= U or float(l_arr[i]) <= L:
                        guard["triggers_in_window"] += 1
                side = 0
                if WIN_START_HR <= hr < WIN_END_HR:
                    if float(h_arr[i]) >= U:
                        side = -1
                    elif float(l_arr[i]) <= L:
                        side = 1
                if side == 0:
                    i += 1
                    continue
                entry = float(c_arr[i])
                stop = entry - side * fixed_pips * PIP
                risk = abs(entry - stop)
                if risk <= 0:
                    i += 1
                    continue
                guard["signals"] += 1
                pos = {"side": side, "entry_i": i, "entry": entry,
                       "stop": stop, "risk": risk, "O": O, "target": O}
                i += 1
                continue

            side = pos["side"]
            exit_px, reason = None, None
            if side == 1:
                if float(l_arr[i]) <= pos["stop"]:
                    exit_px, reason = pos["stop"], "stop"
                elif float(h_arr[i]) >= pos["target"]:
                    exit_px, reason = pos["target"], "target"
            else:
                if float(h_arr[i]) >= pos["stop"]:
                    exit_px, reason = pos["stop"], "stop"
                elif float(l_arr[i]) <= pos["target"]:
                    exit_px, reason = pos["target"], "target"
            if exit_px is None and (i - pos["entry_i"]) >= max_hold:
                exit_px, reason = float(c_arr[i]), "time"
            if exit_px is not None:
                book(d, ts_arr, pos, exit_px, reason, i)
                pos = None
            i += 1

        if pos is not None:
            guard["closed_at_day_end"] += 1
            book(d, ts_arr, pos, float(c_arr[-1]), "day_end", n - 1)

    return trades, guard, hld


def metrics(trades: list[dict], guard: dict, label: str) -> dict:
    if not trades:
        return {"label": label, "n": 0, "guard": guard}
    net_pips = np.array([t["net_pips"] for t in trades], float)
    gross_pips = np.array([t["gross_pips"] for t in trades], float)
    net_R = np.array([t["net_R"] for t in trades], float)
    wins, losses = net_pips[net_pips > 0], net_pips[net_pips <= 0]
    gp = gross_pips[gross_pips > 0].sum()
    gl = -gross_pips[gross_pips <= 0].sum()

    eq = np.cumsum(net_R)
    dd_R = float((eq - np.maximum.accumulate(eq)).min())
    eq_usd = np.cumsum(net_pips) * USD_PER_PIP_1LOT
    dd_usd = float((eq_usd - np.maximum.accumulate(eq_usd)).min())

    reasons = (pd.Series([t["exit_reason"] for t in trades])
               .value_counts().to_dict())
    n_total = len(trades)
    target_n = reasons.get("target", 0)
    stop_n = reasons.get("stop", 0)
    time_n = reasons.get("time", 0)
    day_n = reasons.get("day_end", 0)
    hb = np.array([t["holding_bars"] for t in trades], int)

    out = {
        "label": label, "n": n_total,
        "win_rate": round(len(wins) / n_total, 4),
        "expectancy_R": round(float(net_R.mean()), 4),
        "expectancy_pips": round(float(net_pips.mean()), 3),
        "gross_PF": round(gp / gl, 3) if gl > 0 else None,
        "net_PF": (round(wins.sum() / -losses.sum(), 3)
                   if len(losses) and losses.sum() else None),
        "net_pips_total": round(float(net_pips.sum()), 1),
        "net_usd_1lot": round(float(net_pips.sum()) * USD_PER_PIP_1LOT, 2),
        "max_dd_R": round(dd_R, 2),
        "max_dd_usd_1lot": round(dd_usd, 2),
        "exit_reasons": reasons,
        "target_hit_rate": round(target_n / n_total, 4),
        "stop_hit_rate": round(stop_n / n_total, 4),
        "time_hit_rate": round(time_n / n_total, 4),
        "day_end_rate": round(day_n / n_total, 4),
        "avg_distance_to_O_pips": round(float(np.mean(
            [t["distance_to_O_at_entry_pips"] for t in trades])), 1),
        "holding_bars": {
            "mean": round(float(hb.mean()), 2),
            "median": int(np.median(hb)),
            "p25": int(np.percentile(hb, 25)),
            "p75": int(np.percentile(hb, 75)),
            "max": int(hb.max()),
        },
        "guard": guard,
    }
    if target_n > 0:
        hb_t = np.array([t["holding_bars"] for t in trades
                         if t["exit_reason"] == "target"], int)
        out["holding_bars_when_target"] = {
            "n": int(target_n),
            "mean": round(float(hb_t.mean()), 2),
            "median": int(np.median(hb_t)),
            "min": int(hb_t.min()),
            "max": int(hb_t.max()),
        }
    return out


def yearly(trades: list[dict]) -> list[dict]:
    if not trades:
        return []
    by: dict[int, list[float]] = {}
    for t in trades:
        y = int(t["date"][:4])
        by.setdefault(y, []).append(t["net_pips"])
    out = []
    for y in sorted(by):
        nets = by[y]
        out.append({
            "year": y, "n": len(nets),
            "net_pips": round(sum(nets), 1),
            "net_usd_1lot": round(sum(nets) * USD_PER_PIP_1LOT, 2),
            "win_rate": round(sum(1 for n in nets if n > 0) / len(nets), 3),
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser(
        description="EURUSD Reversal V1 exp02: trigger-threshold sweep on to-O")
    ap.add_argument("--m1", default=str(DEFAULT_M1))
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT))
    ap.add_argument("--fx-day-start", type=int, default=6)
    ap.add_argument("--min-window-bars", type=int, default=20)
    ap.add_argument("--fixed-stop-pips", type=float, default=20.0)
    ap.add_argument("--max-hold-bars", type=int, default=24)
    ap.add_argument("--cost-pips", type=float, default=1.5)
    ap.add_argument("--oos-year", type=int, default=2016)
    args = ap.parse_args()

    m5, quality = load_m5(Path(args.m1))
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    days, day_led = build_days(m5, args.fx_day_start,
                                WIN_START_HR, WIN_END_HR,
                                args.min_window_bars)

    scenarios = [("0.3%", 0.003), ("0.5%", 0.005), ("1.0%", 0.010)]
    results: dict = {}
    for label, pct in scenarios:
        trades, guard, hld = simulate(
            days, pct=pct, fixed_pips=args.fixed_stop_pips,
            max_hold=args.max_hold_bars, cost_pips=args.cost_pips,
            count_triggers=True)
        is_tr = [t for t in trades if int(t["date"][:4]) < args.oos_year]
        oos_tr = [t for t in trades if int(t["date"][:4]) >= args.oos_year]
        results[label] = {
            "pct": pct,
            "full": metrics(trades, guard, label),
            "is": metrics(is_tr, guard, label + "_IS"),
            "oos": metrics(oos_tr, guard, label + "_OOS"),
            "yearly": yearly(trades),
            "trades": trades,
        }
        tdf = pd.DataFrame(trades)
        if len(tdf):
            tdf.to_csv(out / f"exp02_pct{label.replace('.', '_').replace('%', 'pct')}_trades.csv",
                       index=False)

    # Cost sensitivity on the three thresholds (no trigger counter, just n/expR/PF).
    cost_rows = []
    for label, pct in scenarios:
        for c in (0.5, 1.0, 1.5, 2.0, 3.0):
            tr, g, _ = simulate(
                days, pct=pct, fixed_pips=args.fixed_stop_pips,
                max_hold=args.max_hold_bars, cost_pips=c,
                count_triggers=False)
            m = metrics(tr, g, label)
            cost_rows.append({
                "label": label, "cost_pips": c, "n": m["n"],
                "net_PF": m.get("net_PF"),
                "expectancy_R": m.get("expectancy_R"),
                "net_pips_total": m.get("net_pips_total"),
                "target_hit_rate": m.get("target_hit_rate"),
            })

    # JSON report: trade list is huge, write it separately
    report_no_trades = {
        "spec": {
            "purpose": ("exp02: lower the trigger threshold on the to-O + 15-18 + A "
                        "combo to test whether the 1.0% edge is real mean-reversion "
                        "or a 2-hour drift effect."),
            "frozen": {
                "window": "Beijing 15:00-18:00",
                "stop": f"A: fixed {args.fixed_stop_pips} pips",
                "target": "revert to day open O",
                "cost_pips": args.cost_pips,
                "time_stop_bars": args.max_hold_bars,
            },
            "variable": "trigger threshold pct in {0.3%, 0.5%, 1.0%}",
            "1.0%_is_baseline": ("re-run on this code path; not the exp01 number "
                                  "carried over. exp01 numbers: 280 trades, OOS "
                                  "expR +0.439; this run is the in-script "
                                  "apples-to-apples control."),
            "trigger_counting": ("triggers_in_window counts every 5m bar in the "
                                 "configured window whose high >= O*(1+pct) or "
                                 "low <= O*(1-pct), regardless of position state. "
                                 "entries = positions actually opened."),
        },
        "data_quality": {**quality, "window_15_18": day_led},
        "results": {label: {
            "pct": v["pct"],
            "full": v["full"], "is": v["is"], "oos": v["oos"],
            "yearly": v["yearly"],
        } for label, v in results.items()},
        "cost_sensitivity": cost_rows,
    }
    rp = out / "exp02_threshold_report.json"
    rp.write_text(json.dumps(report_no_trades, indent=2, ensure_ascii=False) + "\n",
                  encoding="utf-8")

    # -------------------- console output --------------------
    print("=" * 130)
    print("EURUSD_Reversal_V1 -- Experiment 02: trigger-threshold sweep on to-O")
    print("=" * 130)
    print(f"data  : {quality['m5_bars']:,} 5m bars  {quality['m5_range'][0]} .. {quality['m5_range'][1]}")
    print(f"window: Beijing 15-18  total={day_led['total_days']:,} "
          f"kept={day_led['kept']:,} dropped={day_led['window_not_populated']:,}")
    print(f"frozen: stop A={args.fixed_stop_pips}p, target=O, "
          f"cost={args.cost_pips}p, time={args.max_hold_bars} bars")
    print(f"oos split at year >= {args.oos_year}")
    print("-" * 130)
    print("[A] 触发 vs 入场 vs 全样本表现")
    print(f"  {'pct':<7}{'触发bars':>10}{'入场':>8}{'触发→入场':>12}"
          f"{'n':>6}{'净PF':>8}{'期望R':>9}{'净pips':>11}"
          f"{'maxDD_R':>10}{'maxDD_$':>11}{'avg距O(p)':>11}")
    for label, _ in scenarios:
        m = results[label]["full"]
        g = m["guard"]
        n = m["n"]
        trig = g.get("triggers_in_window", 0)
        eff = f"{n / trig * 100:.1f}%" if trig else "-"
        print(f"  {label:<7}{trig:>10}{g['signals']:>8}{eff:>12}{n:>6}"
              f"{fnum(m.get('net_PF'), '{}'):>8}"
              f"{m.get('expectancy_R', 0):+9.4f}"
              f"{m.get('net_pips_total', 0):+11,.0f}"
              f"{m.get('max_dd_R', 0):+10.2f}"
              f"{m.get('max_dd_usd_1lot', 0):+11,.0f}"
              f"{m.get('avg_distance_to_O_pips', 0):>11.0f}")
    print("-" * 130)
    print("[B] 出场原因 + 持有时间分布")
    print(f"  {'pct':<7}{'target':>8}{'stop':>8}{'time':>8}{'day_end':>10}"
          f"{'O命中%':>9}{'停损%':>9}{'时间%':>9}{'日终%':>9}"
          f"{'平均hold':>10}{'中位':>6}{'P25':>6}{'P75':>6}")
    for label, _ in scenarios:
        m = results[label]["full"]
        er = m["exit_reasons"]
        hb = m["holding_bars"]
        print(f"  {label:<7}{er.get('target', 0):>8}{er.get('stop', 0):>8}"
              f"{er.get('time', 0):>8}{er.get('day_end', 0):>10}"
              f"{m.get('target_hit_rate', 0):>9.1%}"
              f"{m.get('stop_hit_rate', 0):>9.1%}"
              f"{m.get('time_hit_rate', 0):>9.1%}"
              f"{m.get('day_end_rate', 0):>9.1%}"
              f"{hb['mean']:>10.2f}{hb['median']:>6}"
              f"{hb['p25']:>6}{hb['p75']:>6}")
    print()
    print("  O 命中时的持有时间（bars）")
    for label, _ in scenarios:
        m = results[label]["full"]
        if "holding_bars_when_target" in m:
            t = m["holding_bars_when_target"]
            print(f"    {label:<7} n={t['n']:>4}  mean={t['mean']:>5.1f}  "
                  f"median={t['median']:>4}  range=[{t['min']}..{t['max']}]")
        else:
            print(f"    {label:<7} n=0  (从未命中 O)")
    print("-" * 130)
    print(f"[C] IS (<{args.oos_year}) vs OOS (>={args.oos_year})")
    print(f"  {'pct':<7}{'phase':<5}{'n':>6}{'净PF':>8}{'期望R':>9}"
          f"{'净pips':>11}{'O命中%':>9}{'停损%':>9}{'时间%':>9}")
    for label, _ in scenarios:
        for phase in ("is", "oos"):
            m = results[label][phase]
            if not m.get("n"):
                print(f"  {label:<7}{phase:<5}{0:>6}{'-':>8}{'-':>9}"
                      f"{'-':>11}{'-':>9}{'-':>9}{'-':>9}")
                continue
            print(f"  {label:<7}{phase:<5}{m['n']:>6}"
                  f"{fnum(m.get('net_PF'), '{}'):>8}"
                  f"{m.get('expectancy_R', 0):+9.4f}"
                  f"{m.get('net_pips_total', 0):+11,.0f}"
                  f"{m.get('target_hit_rate', 0):>9.1%}"
                  f"{m.get('stop_hit_rate', 0):>9.1%}"
                  f"{m.get('time_hit_rate', 0):>9.1%}")
    print("-" * 130)
    print("[D] 年度收益分布")
    by_pct = {label: {yd["year"]: yd for yd in results[label]["yearly"]}
              for label, _ in scenarios}
    all_years = sorted({y for d in by_pct.values() for y in d})
    print(f"  {'year':<6}", end="")
    for label, _ in scenarios:
        print(f"  n_{label:<5}{'net_'+label:>10}", end="")
    print()
    for y in all_years:
        print(f"  {y:<6}", end="")
        for label, _ in scenarios:
            yd = by_pct[label].get(y)
            if yd:
                print(f"  {yd['n']:>5}{yd['net_pips']:>+10,.0f}", end="")
            else:
                print(f"  {'-':>5}{'-':>10}", end="")
        print()
    print("-" * 130)
    print("[E] 成本敏感性 (cost_pips -> 期望R / 净PF / O命中率)")
    print(f"  {'pct':<7}{'metric':<10}{'0.5':>10}{'1.0':>10}{'1.5':>10}{'2.0':>10}{'3.0':>10}")
    for label, _ in scenarios:
        for metric in ("expectancy_R", "net_PF", "target_hit_rate"):
            row = f"  {label:<7}{metric:<10}"
            for c in (0.5, 1.0, 1.5, 2.0, 3.0):
                r = next((x for x in cost_rows
                          if x["label"] == label and x["cost_pips"] == c), None)
                if r is None or r.get(metric) is None:
                    row += f"{'-':>10}"
                elif metric == "expectancy_R":
                    row += f"{r[metric]:+10.4f}"
                elif metric == "net_PF":
                    row += f"{r[metric]:>10.3f}"
                else:
                    row += f"{r[metric]:>10.1%}"
            print(row)
    print("=" * 130)
    print(f"report  -> {rp}")
    for label, _ in scenarios:
        print(f"trades  -> {out / ('exp02_pct' + label.replace('.', '_').replace('%', 'pct') + '_trades.csv')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
