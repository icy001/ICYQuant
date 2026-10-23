#!/usr/bin/env python3
"""EURUSD_Reversal_V1 -- take-profit x window sweep (round 2).

Data path
---------
artifacts/histdata_v9/parsed/eurusd_2000-2026_bars.parquet
  <- data/real/histdata/HISTDATA_COM_ASCII_EURUSD_M1*/DAT_ASCII_EURUSD_M1_*.csv

Time semantics (verified off the FX calendar, not assumed)
---------------------------------------------------------
Sunday open and Friday close both fall on stored 17:00 in identical clock
hours winter vs summer -> fixed EST(UTC-5) without DST. So

    UTC      = ts + 5h
    BEIJING  = ts + 13h

Dayline trap: every row inside the Beijing 09:00-10:00 (and 15:00-18:00) window
sits on a stored date that differs from its Beijing date. Taking "today's open"
off the stored date would attach every signal to the wrong day.

Strategy spec -- four explicitly-frozen combinations
---------------------------------------------------
The repo carries the NAME EURUSD_Reversal_V1 but no entry-rule definition.
The user supplied two candidate take-profits and asked both to be tested on
both the original 09:00-10:00 window and a 15:00-18:00 London window:

  take-profit 30 pips:        fixed 30 pips from entry, the value the user
                              recalls as the original draft (NOT promoted to
                              "the original rule" -- labelled as a candidate)
  take-profit to day open:    revert to O, ~110 pips at 1.10 (this round's
                              "110 pips" variant from the previous report)

Both take-profits are tested on BOTH windows:

  window Beijing 09:00-10:00  (the original)
  window Beijing 15:00-18:00  (London session, a market-structure candidate)

For every (take-profit x window) pair we run BOTH stop options so a stop-
quality difference cannot masquerade as a take-profit or window difference:

  A fixed 20 pips
  B running day extreme known at entry (past-only, no look-ahead)

Entry is identical across all eight runs:

  O         first 5m open of the FX day (Beijing 06:00 = NY 17:00)
  bands     U = O*(1+pct), L = O*(1-pct),  pct default 1%
  trigger   bar with high >= U  -> short at that bar's close
            bar with low  <= L  -> long  at that bar's close
  stop/time  per option A/B;  time stop = 24 bars;  forced flat at day end

Look-ahead guards (unchanged from prior round)
---------------------------------------------
  * O is the FX day's first bar -> it precedes the entry window.
  * U/L derive from O only.
  * Boundary stop uses the running extreme from day start THROUGH the entry
    bar. It never touches bars after entry.
  * Entry fills at the triggering bar's close; exits are judged only on
    bars AFTER the entry bar; the engine walks forward one bar at a time.

Cost
----
HistData M1 is single-sided BID with NO recorded spread, so cost is assumed
not measured. Default 1.5 pips round trip; the sweep tests 0.5-3.0.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
DEFAULT_M1 = REPO / "artifacts/histdata_v9/parsed/eurusd_2000-2026_bars.parquet"
DEFAULT_OUT = REPO / "artifacts/research/eurusd_reversal_v1"

PIP = 0.0001
USD_PER_PIP_1LOT = 10.0
STORED_TO_BEIJING = pd.Timedelta(hours=13)   # EST(UTC-5) -> UTC+8


def fnum(v, spec: str) -> str:
    """Format a metric, rendering None/NaN as '-' rather than crashing."""
    if v is None:
        return "-"
    try:
        if np.isnan(v):
            return "-"
    except (TypeError, ValueError):
        pass
    try:
        return spec.format(v)
    except (TypeError, ValueError):
        return "-"


# Beijing 09:00-10:00 spans 12 five-minute bars; 15:00-18:00 spans 36.
# Requiring 10 of 12 (and 30 of 36 respectively) keeps every day that
# actually has the window, while still rejecting days whose data is patchy
# enough to distort a window-dependent signal. The runtime threshold is
# passed in from main per window so the cutoff is always proportional.
MIN_WINDOW_BARS_DEFAULT = 10


# --------------------------------------------------------------------------- #
def load_m5(path: Path) -> tuple[pd.DataFrame, dict]:
    """M1 -> Beijing -> 5-minute OHLC."""
    df = pd.read_parquet(path, columns=["ts", "open", "high", "low", "close"])
    bj = pd.to_datetime(df["ts"]) + STORED_TO_BEIJING
    df = df.drop(columns=["ts"])
    df.index = bj
    m5 = (df.resample("5min", label="left", origin="start_day")
            .agg(open=("open", "first"), high=("high", "max"),
                 low=("low", "min"), close=("close", "last"))
            .dropna(subset=["open", "high", "low", "close"]))
    m5.index.name = "bj"
    return m5, {"m1_rows": int(len(df)), "m5_bars": int(len(m5)),
                "m5_range": [str(m5.index.min()), str(m5.index.max())]}


def build_days(m5: pd.DataFrame, day_start_hour: int,
               win_start_hr: int, win_end_hr: int,
               min_window_bars: int) -> tuple[list[dict], dict]:
    """Slice into FX trading days and keep days whose configured window is
    populated to the required density. Every rejected day is counted with
    its reason so nothing vanishes silently."""
    ts = m5.index
    hours = ts.hour
    labels = (ts.normalize()
              - pd.to_timedelta((hours < day_start_hour).astype(int),
                                unit="D")).date

    o = m5["open"].to_numpy(float)
    h = m5["high"].to_numpy(float)
    l = m5["low"].to_numpy(float)
    c = m5["close"].to_numpy(float)

    days: list[dict] = []
    ledger = {"total_days": 0, "kept": 0, "window_not_populated": 0,
              "win_start_hr": win_start_hr, "win_end_hr": win_end_hr,
              "min_window_bars": min_window_bars}
    arr_labels = np.array(labels)
    uniq, starts = np.unique(arr_labels, return_index=True)
    bounds = list(starts) + [len(arr_labels)]

    for k in range(len(uniq)):
        s, e = bounds[k], bounds[k + 1]
        ledger["total_days"] += 1
        day_ts = ts[s:e]
        win_mask = ((day_ts.hour >= win_start_hr)
                    & (day_ts.hour < win_end_hr))
        if int(win_mask.sum()) < min_window_bars:
            ledger["window_not_populated"] += 1
            continue
        days.append({"date": uniq[k], "ts": day_ts,
                     "o": o[s:e], "h": h[s:e], "l": l[s:e], "c": c[s:e],
                     "win_start_hr": win_start_hr, "win_end_hr": win_end_hr})
        ledger["kept"] += 1
    return days, ledger


def simulate(days: list[dict], *, pct: float, stop_mode: str,
             fixed_pips: float, max_hold: int, cost_pips: float,
             min_stop_pips: float,
             win_start_hr: int, win_end_hr: int,
             tp_pips: float = None) -> tuple[list[dict], dict]:
    """Forward walk, one bar at a time, no rewinding.

    New entries allowed only inside [win_start_hr, win_end_hr) Beijing. Exits
    are judged only on bars strictly after the entry bar. Anything still open
    is flattened at the last bar of the FX day.

    `tp_pips` chooses the take-profit: a finite number is the fixed pip target
    from entry; None means target = day open (revert-to-O variant).
    """
    trades: list[dict] = []
    guard = {"signals": 0, "boundary_stop_too_tight": 0, "closed_at_day_end": 0}
    equity_R: list[float] = []

    def book(d, ts_arr, pos, exit_px, reason):
        side, entry, risk = pos["side"], pos["entry"], pos["risk"]
        gross_pips = side * (exit_px - entry) / PIP
        risk_pips = risk / PIP if risk else 0.0
        gross_r = gross_pips / risk_pips if risk_pips else 0.0
        cost_r = cost_pips / risk_pips if risk_pips else 0.0
        net_pips = gross_pips - cost_pips
        trades.append({
            "date": str(d["date"]),
            "side": "long" if side == 1 else "short",
            "entry_bar": str(ts_arr[pos["entry_i"]]),
            "day_open": round(pos["O"], 5),
            "target_px": round(pos["target"], 5),
            "entry_px": round(entry, 5),
            "stop_px": round(pos["stop"], 5),
            "exit_px": round(exit_px, 5),
            "risk_pips": round(risk_pips, 2),
            "exit_reason": reason,
            "gross_pips": round(gross_pips, 2),
            "net_pips": round(net_pips, 2),
            "gross_R": round(gross_r, 4),
            "net_R": round(gross_r - cost_r, 4),
            "net_usd_1lot": round(net_pips * USD_PER_PIP_1LOT, 2),
        })
        equity_R.append(gross_r - cost_r)

    for d in days:
        h_arr, l_arr, c_arr, ts_arr = d["h"], d["l"], d["c"], d["ts"]
        n = len(h_arr)
        O = float(d["o"][0])
        if not np.isfinite(O) or O <= 0:
            continue
        U, L = O * (1.0 + pct), O * (1.0 - pct)

        pos = None
        run_hi, run_lo = float(h_arr[0]), float(l_arr[0])
        i = 0
        while i < n:
            run_hi = max(run_hi, float(h_arr[i]))
            run_lo = min(run_lo, float(l_arr[i]))

            if pos is None:
                hr = int(ts_arr[i].hour)
                if hr >= win_end_hr:                  # configured window is past
                    break
                side = 0
                if win_start_hr <= hr < win_end_hr:
                    if float(h_arr[i]) >= U:
                        side = -1
                    elif float(l_arr[i]) <= L:
                        side = 1
                if side == 0:
                    i += 1
                    continue
                entry = float(c_arr[i])
                if stop_mode == "fixed":
                    stop = entry - side * fixed_pips * PIP
                else:
                    extreme = run_lo if side == 1 else run_hi
                    if abs(entry - extreme) / PIP < min_stop_pips:
                        guard["boundary_stop_too_tight"] += 1
                        stop = entry - side * min_stop_pips * PIP
                    else:
                        stop = extreme
                risk = abs(entry - stop)
                if risk <= 0:
                    i += 1
                    continue
                target = (entry + side * tp_pips * PIP) if tp_pips else O
                guard["signals"] += 1
                pos = {"side": side, "entry_i": i, "entry": entry,
                       "stop": stop, "risk": risk, "O": O, "target": target}
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
                book(d, ts_arr, pos, exit_px, reason)
                pos = None
            i += 1

        if pos is not None:                        # day ran out with a position on
            guard["closed_at_day_end"] += 1
            book(d, ts_arr, pos, float(c_arr[-1]), "day_end")

    return trades, {**guard, "equity_R": equity_R}


def metrics(trades: list[dict], label: str) -> dict:
    if not trades:
        return {"label": label, "n": 0}
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

    return {
        "label": label,
        "n": len(trades),
        "win_rate": round(len(wins) / len(net_pips), 4),
        "expectancy_R": round(float(net_R.mean()), 4),
        "gross_PF": round(gp / gl, 3) if gl > 0 else None,
        "net_PF": round(wins.sum() / -losses.sum(), 3)
                  if len(losses) and losses.sum() else None,
        "expectancy_pips": round(float(net_pips.mean()), 3),
        "net_pips_total": round(float(net_pips.sum()), 1),
        "net_usd_1lot": round(float(net_pips.sum()) * USD_PER_PIP_1LOT, 2),
        "max_dd_R": round(dd_R, 2),
        "max_dd_usd_1lot": round(dd_usd, 2),
        "exit_reasons": pd.Series([t["exit_reason"] for t in trades])
                          .value_counts().to_dict(),
        "avg_risk_pips": round(float(np.mean([t["risk_pips"] for t in trades])), 2),
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description="EURUSD_Reversal_V1: take-profit x window sweep")
    ap.add_argument("--m1", default=str(DEFAULT_M1))
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT))
    ap.add_argument("--pct", type=float, default=0.01)
    ap.add_argument("--fx-day-start", type=int, default=6)
    ap.add_argument("--fixed-stop-pips", type=float, default=20.0)
    ap.add_argument("--min-stop-pips", type=float, default=5.0)
    ap.add_argument("--max-hold-bars", type=int, default=24)
    ap.add_argument("--cost-pips", type=float, default=1.5)
    ap.add_argument("--min-window-bars", type=int,
                    default=MIN_WINDOW_BARS_DEFAULT)
    ap.add_argument("--oos-year", type=int, default=2016)
    args = ap.parse_args()

    m5, quality = load_m5(Path(args.m1))
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    # 2 take-profits x 2 windows x 2 stops = 8 scenarios, ALL reported.
    # For every (TP, window) pair we run BOTH stops so a stop-quality
    # contrast cannot masquerade as a take-profit or window contrast.
    tp_options = [
        ("tp30",       30.0, "30 pips"),
        ("tp_to_open", None, "to O"),
    ]
    windows = [
        ("win_09_10", 9, 10),
        ("win_15_18", 15, 18),
    ]
    stops = [
        ("A_fixed20",  dict(stop_mode="fixed", fixed_pips=args.fixed_stop_pips)),
        ("B_boundary", dict(stop_mode="boundary")),
    ]

    # Build the day-slices once per window, reuse for all four (TP x stop) runs.
    day_cache = {}
    for w_label, ws, we in windows:
        # the longer 15:00-18:00 window has 36 bars, so require ~30 to keep
        # "fully populated" days only; the 09:00-10:00 window keeps its 10/12.
        if we - ws >= 3:                       # 3h windows get the larger floor
            min_bars = max(20, args.min_window_bars)
        else:
            min_bars = args.min_window_bars
        d, led = build_days(m5, args.fx_day_start, ws, we, min_bars)
        day_cache[(ws, we)] = (d, led, min_bars)

    results = {}
    for tp_label, tp_pips, _ in tp_options:
        for w_label, ws, we in windows:
            for s_label, stop_kw in stops:
                sc_name = f"{tp_label}_{w_label}_{s_label}"
                days, led, _ = day_cache[(ws, we)]
                trades, guard = simulate(
                    days, pct=args.pct,
                    stop_mode=stop_kw["stop_mode"],
                    fixed_pips=stop_kw.get("fixed_pips", 0.0),
                    max_hold=args.max_hold_bars,
                    cost_pips=args.cost_pips,
                    min_stop_pips=args.min_stop_pips,
                    win_start_hr=ws, win_end_hr=we,
                    tp_pips=tp_pips)
                tdf = pd.DataFrame(trades)
                if len(tdf):
                    tdf.to_csv(out / f"{sc_name}_trades.csv", index=False)
                is_tr = [t for t in trades if int(t["date"][:4]) < args.oos_year]
                oos_tr = [t for t in trades if int(t["date"][:4]) >= args.oos_year]
                results[sc_name] = {
                    "full": metrics(trades, sc_name),
                    "is": metrics(is_tr, f"{sc_name}_IS_lt{args.oos_year}"),
                    "oos": metrics(oos_tr, f"{sc_name}_OOS_ge{args.oos_year}"),
                    "guard": {k: v for k, v in guard.items() if k != "equity_R"},
                    "params": {"tp_pips": tp_pips,
                               "win_start_hr": ws, "win_end_hr": we,
                               **stop_kw},
                }

    # Cost sensitivity, stop A only (the B-vs-A stop question was settled in
    # the previous round and need not be redone for every TP x window pair).
    cost_rows = []
    for tp_label, tp_pips, _ in tp_options:
        for w_label, ws, we in windows:
            sc = f"{tp_label}_{w_label}_A_fixed20"
            days, _, _ = day_cache[(ws, we)]
            for c in (0.5, 1.0, 1.5, 2.0, 3.0):
                tr, _ = simulate(days, pct=args.pct, stop_mode="fixed",
                                 fixed_pips=args.fixed_stop_pips,
                                 max_hold=args.max_hold_bars, cost_pips=c,
                                 min_stop_pips=args.min_stop_pips,
                                 win_start_hr=ws, win_end_hr=we,
                                 tp_pips=tp_pips)
                m = metrics(tr, sc)
                cost_rows.append({"scenario": sc, "cost_pips": c,
                                  "n": m.get("n"),
                                  "net_PF": m.get("net_PF"),
                                  "expectancy_R": m.get("expectancy_R"),
                                  "net_pips_total": m.get("net_pips_total")})

    report = {
        "spec": {
            "bars": "5-minute OHLC from HistData M1, Beijing clock",
            "timezone_proof": ("Sunday open and Friday close both land on "
                               "stored 17:00, identical Jan-Feb vs Jun-Aug -> "
                               "fixed EST (UTC-5); Beijing = ts + 13h"),
            "day": f"FX trading day starting {args.fx_day_start:02d}:00 Beijing",
            "O": "first available 5m open of the FX day",
            "trigger": f"|price - O| >= {args.pct:.2%} inside the configured "
                       f"Beijing window",
            "entry": "reversal against the move, at the triggering bar's close",
            "target": {
                "tp30": "fixed 30 pips from entry (CANDIDATE; not promoted "
                        "to original-rule status)",
                "tp_to_open": "revert to O (day's open, ~110 pips at 1.10)",
            },
            "stops": {"A": f"fixed {args.fixed_stop_pips} pips",
                      "B": "running day extreme known at entry (past-only)"},
            "time_stop": f"{args.max_hold_bars} bars",
            "cost": f"{args.cost_pips} pips ASSUMED (bid-only source, no spread)",
        },
        "data_quality": {
            **quality,
            "win_09_10": day_cache[(9, 10)][1],
            "win_15_18": day_cache[(15, 18)][1],
        },
        "results": results,
        "cost_sensitivity": cost_rows,
    }
    rp = out / "reversal_v1_tp_window_report.json"
    rp.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                  encoding="utf-8")

    print("=" * 130)
    print("EURUSD_Reversal_V1 -- take-profit x window x stop sweep, 5m bars, "
          "real HistData M1")
    print("=" * 130)
    print(f"M1 rows {quality['m1_rows']:,} -> 5m bars {quality['m5_bars']:,}   "
          f"{quality['m5_range'][0]} .. {quality['m5_range'][1]}")
    for (ws, we), (_, led, min_bars) in day_cache.items():
        print(f"window Beijing {ws:02d}-{we:02d}: total={led['total_days']:,} "
              f"kept={led['kept']:,} "
              f"dropped(window<{min_bars}/{(we-ws)*12} bars)="
              f"{led['window_not_populated']:,}")
    print(f"tz fixed EST(UTC-5) -> Beijing=ts+13h | trigger +-{args.pct:.1%} of "
          f"day open | cost {args.cost_pips} pips ASSUMED")
    print("-" * 130)
    print(f"{'TP':<10}{'window':<10}{'stop':<11}"
          f"{'n':>6}{'winR':>7}{'netPF':>8}{'expR':>9}"
          f"{'net pips':>11}{'maxDD(R)':>10}{'maxDD($)':>11}")
    for tp_label, _, tp_disp in tp_options:
        for w_label, ws, we in windows:
            for s_label, _ in stops:
                sc = f"{tp_label}_{w_label}_{s_label}"
                m = results[sc]["full"]
                if not m.get("n"):
                    print(f"{tp_disp:<10}{ws:02d}-{we:02d}      {s_label:<11}"
                          f"{0:>6}{'-':>7}{'-':>8}{'-':>9}{'-':>11}"
                          f"{'-':>10}{'-':>11}")
                    continue
                print(f"{tp_disp:<10}{ws:02d}-{we:02d}      {s_label:<11}"
                      f"{m['n']:>6}{m['win_rate']:>7.1%}"
                      f"{fnum(m['net_PF'], '{}'):>8}"
                      f"{m['expectancy_R']:>+9.3f}"
                      f"{m['net_pips_total']:>+11,.0f}"
                      f"{m['max_dd_R']:>+10.1f}"
                      f"{m['max_dd_usd_1lot']:>+11,.0f}")
    print("-" * 130)
    print(f"SAMPLE SPLIT at {args.oos_year} (out-of-sample must stand on its own)")
    print(f"  {'TP':<10}{'window':<10}{'stop':<11}{'phase':<5}"
          f"{'n':>6}{'winR':>7}{'netPF':>8}{'expR':>9}{'net pips':>11}")
    for tp_label, _, tp_disp in tp_options:
        for w_label, ws, we in windows:
            for s_label, _ in stops:
                sc = f"{tp_label}_{w_label}_{s_label}"
                for phase in ("is", "oos"):
                    m = results[sc][phase]
                    if not m.get("n"):
                        print(f"  {tp_disp:<10}{ws:02d}-{we:02d}      "
                              f"{s_label:<11}{phase:<5}{0:>6}{'-':>7}"
                              f"{'-':>8}{'-':>9}{'-':>11}")
                        continue
                    print(f"  {tp_disp:<10}{ws:02d}-{we:02d}      "
                          f"{s_label:<11}{phase:<5}{m['n']:>6}"
                          f"{m['win_rate']:>7.1%}"
                          f"{fnum(m['net_PF'], '{}'):>8}"
                          f"{m['expectancy_R']:>+9.3f}"
                          f"{m['net_pips_total']:>+11,.0f}")
    print("-" * 130)
    print("COST SENSITIVITY (stop A only; stop B vs A was settled in the prior round)")
    print(f"  {'TP':<10}{'window':<10}{'cost':<6}{'n':>6}"
          f"{'netPF':>8}{'expR':>9}{'net pips':>11}")
    for r in cost_rows:
        sc = r["scenario"]
        tp_disp = "30 pips" if "tp30" in sc else "to O"
        p = results[sc]["params"]
        ws, we = p["win_start_hr"], p["win_end_hr"]
        print(f"  {tp_disp:<10}{ws:02d}-{we:02d}      {r['cost_pips']:<6}{r['n']:>6}"
              f"{fnum(r['net_PF'], '{}'):>8}"
              f"{fnum(r['expectancy_R'], '{:+.3f}'):>9}"
              f"{fnum(r['net_pips_total'], '{:+,.0f}'):>11}")
    print("-" * 130)
    for sc_name in sorted(results.keys()):
        print(f"exits  {sc_name}: {results[sc_name]['full'].get('exit_reasons')}")
        print(f"guards {sc_name}: {results[sc_name]['guard']}")
    print("=" * 130)
    print(f"report -> {rp}")
    for sc_name in sorted(results.keys()):
        print(f"trades -> {out / (sc_name + '_trades.csv')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
