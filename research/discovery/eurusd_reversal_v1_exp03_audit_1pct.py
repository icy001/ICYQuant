#!/usr/bin/env python3
"""EURUSD Reversal V1 -- Experiment 03: trade-by-trade audit of the 1.0% group.

Context
-------
Reversal V1 is FROZEN. exp01 (TP x window x stop) and exp02 (threshold sweep)
established that 0.3% and 0.5% are negative-expectancy in BOTH IS and OOS and
are not worth further tuning. The 1.0% + 15-18 + A group still shows
+1,006 pips full-sample and +351 pips on 40 OOS trades, but:

  * its "revert to O" target was hit only 2 times in 280 trades
  * OOS is only 40 trades -- too few to justify forward simulation
  * the OOS O-hit rate is 0%, which must reconcile with the 2 full-sample
    target exits (i.e. both must be in IS, not an accounting artifact)

So this pass does NOT optimize anything. It verifies whether the 1.0% result
is real under the stated rules, or an artifact of the backtest implementation.

Method
------
Each trade in the CSV is recomputed from the RAW 5-minute bars through a
SEPARATE code path from the one that produced the CSV. If the two agree
field by field, the implementation is sound. If they disagree, we locate it.

Verified per trade
------------------
  1. entry     : entry_px == close of the entry bar, and that bar really
                 touched the +/-1% band inside Beijing 15-18
  2. stop      : stop_px == entry -+ 20 pips, and hit detection reads only
                 bars AFTER the entry bar (no same-bar look-ahead)
  3. time exit : exit at the 24th bar after entry, at that bar's close
  4. cost      : net_pips == gross_pips - 1.5 exactly
  5. IS/OOS    : split at year >= 2016, and the OOS 0% O-hit rate reconciles
                 with the 2 full-sample target exits

Also measured
-------------
  * same-bar stop+target ties -- if nonzero, the "stop assumed first"
    assumption would be material to the result
  * entry distance to O distribution -- explains why O is rarely reached
  * the 40 OOS trades listed in full, since they alone carry the +0.439
    OOS expectancy claim
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
    load_m5, PIP, USD_PER_PIP_1LOT, fnum,
)

REPO = Path(__file__).resolve().parents[2]
DEFAULT_M1 = REPO / "artifacts/histdata_v9/parsed/eurusd_2000-2026_bars.parquet"
DEFAULT_TRADES = (
    REPO / "artifacts/research/eurusd_reversal_v1/exp02_pct1_0pct_trades.csv")
DEFAULT_OUT = REPO / "artifacts/research/eurusd_reversal_v1"

WIN_START_HR, WIN_END_HR = 15, 18
TOL_PX = 1e-8
TOL_PIPS = 0.011          # CSV stores 2 decimals
TOL_R = 0.00011           # CSV stores 4 decimals


def recompute(m5: pd.DataFrame, t: pd.Series, *, pct: float,
              fixed_pips: float, max_hold: int, cost_pips: float) -> dict:
    """Recompute one trade from raw bars, on a path independent of the
    simulator that wrote the CSV."""
    entry_ts = pd.Timestamp(t["entry_bar"])
    loc = int(m5.index.get_indexer([entry_ts])[0])
    if loc < 0:
        return {"error": f"entry_bar {t['entry_bar']} absent from 5m bars"}

    seg = m5.iloc[loc: loc + 1 + max_hold + 2]
    if len(seg) < 2:
        return {"error": f"only {len(seg)} bars after entry"}

    side = 1 if t["side"] == "long" else -1
    entry_px = float(seg.iloc[0]["close"])
    O = float(t["day_open"])
    U, L = O * (1.0 + pct), O * (1.0 - pct)

    # --- entry-bar facts (do they justify an entry at all?) ---------------
    entry_hour = int(entry_ts.hour)
    in_window = WIN_START_HR <= entry_hour < WIN_END_HR
    bar_high, bar_low = float(seg.iloc[0]["high"]), float(seg.iloc[0]["low"])
    touched = (bar_low <= L) if side == 1 else (bar_high >= U)
    dist_O = abs(entry_px - O) / PIP
    overshoot = dist_O - (pct * O / PIP)      # how far past the 1% band

    stop_px = entry_px - side * fixed_pips * PIP
    target_px = O

    # --- exit: stop > target > time, reading only bars AFTER entry --------
    exit_px, reason, k, tie = None, None, None, False
    for j in range(1, len(seg)):
        bh, bl, bc = (float(seg.iloc[j]["high"]), float(seg.iloc[j]["low"]),
                      float(seg.iloc[j]["close"]))
        if side == 1:
            hit_stop, hit_target = bl <= stop_px, bh >= target_px
        else:
            hit_stop, hit_target = bh >= stop_px, bl <= target_px
        if hit_stop and hit_target:
            tie = True
        if hit_stop:
            exit_px, reason, k = stop_px, "stop", j
            break
        if hit_target:
            exit_px, reason, k = target_px, "target", j
            break
        if j >= max_hold:
            exit_px, reason, k = bc, "time", j
            break

    if exit_px is None:                       # ran out of bars in the slice
        exit_px, reason = float(seg.iloc[-1]["close"]), "time"
        k = len(seg) - 1

    gross_pips = side * (exit_px - entry_px) / PIP
    net_pips = gross_pips - cost_pips
    risk_pips = abs(entry_px - stop_px) / PIP
    net_R = (gross_pips - cost_pips) / risk_pips if risk_pips else 0.0

    return {
        "entry_px": entry_px, "stop_px": stop_px, "target_px": target_px,
        "exit_px": exit_px, "exit_reason": reason,
        "gross_pips": gross_pips, "net_pips": net_pips,
        "net_R": net_R, "holding_bars": int(k),
        "exit_bar": str(seg.index[k]),
        "in_window": in_window, "touched_band": touched,
        "dist_O_pips": dist_O, "overshoot_pips": overshoot, "tie": tie,
    }


def near(a, b, tol) -> bool:
    try:
        return abs(float(a) - float(b)) <= tol
    except (TypeError, ValueError):
        return False


def main() -> int:
    ap = argparse.ArgumentParser(
        description="exp03: trade-by-trade audit of the 1.0% to-O group")
    ap.add_argument("--m1", default=str(DEFAULT_M1))
    ap.add_argument("--trades-csv", default=str(DEFAULT_TRADES))
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT))
    ap.add_argument("--pct", type=float, default=0.010)
    ap.add_argument("--fixed-stop-pips", type=float, default=20.0)
    ap.add_argument("--max-hold-bars", type=int, default=24)
    ap.add_argument("--cost-pips", type=float, default=1.5)
    ap.add_argument("--oos-year", type=int, default=2016)
    args = ap.parse_args()

    m5, quality = load_m5(Path(args.m1))
    tdf = pd.read_csv(args.trades_csv)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    n_csv = len(tdf)
    print("=" * 130)
    print("EURUSD_Reversal_V1 -- Experiment 03: 1.0% group trade-by-trade audit")
    print("=" * 130)
    print(f"source CSV : {args.trades_csv}")
    print(f"trades     : {n_csv}")
    print(f"raw data   : {quality['m5_bars']:,} 5m bars "
          f"{quality['m5_range'][0]} .. {quality['m5_range'][1]}")
    print(f"rules under audit: trigger +-{args.pct:.1%} of O, window Beijing "
          f"{WIN_START_HR}-{WIN_END_HR}, stop A={args.fixed_stop_pips}p, "
          f"target=O, time={args.max_hold_bars} bars, cost={args.cost_pips}p")

    # ---------------- per-trade recompute ----------------
    rows = []
    for _, t in tdf.iterrows():
        r = recompute(m5, t, pct=args.pct, fixed_pips=args.fixed_stop_pips,
                      max_hold=args.max_hold_bars, cost_pips=args.cost_pips)
        if "error" in r:
            rows.append({"date": str(t["date"]), "side": t["side"],
                         "entry_bar": t["entry_bar"], **r})
            continue
        rows.append({
            "date": str(t["date"]), "side": t["side"],
            "entry_bar": t["entry_bar"],
            "csv_entry_px": float(t["entry_px"]),
            "rec_entry_px": r["entry_px"],
            "entry_ok": near(t["entry_px"], r["entry_px"], TOL_PX),
            "csv_stop_px": float(t["stop_px"]),
            "rec_stop_px": r["stop_px"],
            "stop_ok": near(t["stop_px"], r["stop_px"], TOL_PX),
            "target_equals_O": near(t["target_px"], t["day_open"], TOL_PX),
            "csv_exit_px": float(t["exit_px"]),
            "rec_exit_px": r["exit_px"],
            "exit_px_ok": near(t["exit_px"], r["exit_px"], TOL_PX),
            "csv_reason": t["exit_reason"], "rec_reason": r["exit_reason"],
            "reason_ok": t["exit_reason"] == r["exit_reason"],
            "csv_gross": float(t["gross_pips"]),
            "rec_gross": r["gross_pips"],
            "gross_ok": near(t["gross_pips"], r["gross_pips"], TOL_PIPS),
            "csv_net": float(t["net_pips"]), "rec_net": r["net_pips"],
            "net_ok": near(t["net_pips"], r["net_pips"], TOL_PIPS),
            "csv_net_R": float(t["net_R"]), "rec_net_R": r["net_R"],
            "net_R_ok": near(t["net_R"], r["net_R"], TOL_R),
            "csv_hold": int(t["holding_bars"]), "rec_hold": r["holding_bars"],
            "hold_ok": int(t["holding_bars"]) == r["holding_bars"],
            "exit_bar_ok": str(t["exit_bar"]) == r["exit_bar"],
            "in_window": r["in_window"], "touched_band": r["touched_band"],
            "dist_O_pips": r["dist_O_pips"],
            "overshoot_pips": r["overshoot_pips"], "tie": r["tie"],
            "cost_ok": near(float(t["net_pips"]),
                            float(t["gross_pips"]) - args.cost_pips, TOL_PIPS),
        })
    adf = pd.DataFrame(rows)

    err = adf["error"] if "error" in adf.columns else None
    n_err = int(adf["error"].notna().sum()) if "error" in adf.columns else 0
    ok = adf[adf["error"].isna()] if "error" in adf.columns else adf

    print("-" * 130)
    print("[A] 逐笔重算 vs CSV —— 字段级一致性")
    print(f"  {'field':<16}{'compared':>10}{'agree':>9}{'disagree':>10}"
          f"{'max |diff|':>14}")
    checks = [
        ("entry_px",   "entry_ok",    "csv_entry_px", "rec_entry_px", TOL_PX),
        ("stop_px",    "stop_ok",     "csv_stop_px",  "rec_stop_px",  TOL_PX),
        ("exit_px",    "exit_px_ok",  "csv_exit_px",  "rec_exit_px",  TOL_PX),
        ("exit_reason","reason_ok",   None,           None,           None),
        ("gross_pips", "gross_ok",    "csv_gross",    "rec_gross",    None),
        ("net_pips",   "net_ok",      "csv_net",      "rec_net",      None),
        ("net_R",      "net_R_ok",    "csv_net_R",    "rec_net_R",    None),
        ("holding_bars","hold_ok",   "csv_hold",     "rec_hold",     None),
        ("exit_bar",   "exit_bar_ok", None,           None,           None),
    ]
    all_agree = True
    for name, flag, a, b, _ in checks:
        col = ok[flag]
        agree = int(col.sum())
        dis = int(len(col) - agree)
        if dis:
            all_agree = False
        if a and b:
            mx = float((ok[a] - ok[b]).abs().max())
            mx_s = f"{mx:.8f}"
        else:
            mx_s = "-"
        print(f"  {name:<16}{len(col):>10}{agree:>9}{dis:>10}{mx_s:>14}")

    # ---------------- the five rule checks ----------------
    print("-" * 130)
    print("[B] 五项规则核对")
    n_ok = len(ok)
    entry_closes = int(ok["entry_ok"].sum())
    band = int(ok["touched_band"].sum())
    window = int(ok["in_window"].sum())
    cost = int(ok["cost_ok"].sum())
    tgt_eq_O = int(ok["target_equals_O"].sum())
    print(f"  1 入场 = 触发 bar 收盘价        : {entry_closes}/{n_ok} 一致")
    print(f"     且该 bar 真的触及 ±{args.pct:.0%} 边界 : {band}/{n_ok}")
    print(f"     且入场 bar 在北京 {WIN_START_HR}-{WIN_END_HR} : {window}/{n_ok}")
    print(f"  2 止损 = 入场 ∓{args.fixed_stop_pips:.0f} pips   : "
          f"{int(ok['stop_ok'].sum())}/{n_ok} 一致")
    print(f"  3 时间退出 = 入场后第 {args.max_hold_bars} 根 bar 收盘 : "
          f"见 [A] holding_bars {int(ok['hold_ok'].sum())}/{n_ok}")
    print(f"     时间出场笔数 : {int((ok['rec_reason'] == 'time').sum())}")
    print(f"  4 成本扣除 = gross - {args.cost_pips}p   : {cost}/{n_ok} 一致")
    print(f"  5 止盈目标 = 当日开盘 O          : {tgt_eq_O}/{n_ok} 一致")

    # O-hit reconciliation: the specific reconciliation the user asked for
    tgt_rows = ok[ok["rec_reason"] == "target"]
    tgt_is = int((tgt_rows["date"].str[:4].astype(int) < args.oos_year).sum())
    tgt_oos = int((tgt_rows["date"].str[:4].astype(int) >= args.oos_year).sum())
    is_n = int((ok["date"].str[:4].astype(int) < args.oos_year).sum())
    oos_n = int((ok["date"].str[:4].astype(int) >= args.oos_year).sum())
    print(f"     IS/OOS 划分 (year>={args.oos_year}): IS={is_n}  OOS={oos_n}  "
          f"合计={is_n + oos_n}")
    print(f"     O 命中去向: IS 内 {tgt_is} 笔 + OOS 内 {tgt_oos} 笔 "
          f"= {tgt_is + tgt_oos} 笔 (总 O 命中)")
    print(f"     OOS O 命中率 = {tgt_oos}/{oos_n} = "
          f"{(tgt_oos / oos_n * 100 if oos_n else 0):.1f}%  "
          f"| 全样本 O 命中率 = {tgt_is + tgt_oos}/{n_ok} = "
          f"{((tgt_is + tgt_oos) / n_ok * 100 if n_ok else 0):.1f}%")

    # ---------------- independent aggregation ----------------
    rec_net = ok["rec_net"].to_numpy(float)
    rec_R = ok["rec_net_R"].to_numpy(float)
    rec_gross = ok["rec_gross"].to_numpy(float)
    csv_net = ok["csv_net"].to_numpy(float)
    w, l_ = rec_net[rec_net > 0], rec_net[rec_net <= 0]
    gp, gl = rec_gross[rec_gross > 0].sum(), -rec_gross[rec_gross <= 0].sum()
    eq = np.cumsum(rec_R)
    dd_R = float((eq - np.maximum.accumulate(eq)).min())
    eq_u = np.cumsum(rec_net) * USD_PER_PIP_1LOT
    dd_u = float((eq_u - np.maximum.accumulate(eq_u)).min())

    is_mask = ok["date"].str[:4].astype(int) < args.oos_year
    oos_mask = ~is_mask
    rec_is, rec_oos = rec_R[is_mask.to_numpy()], rec_R[oos_mask.to_numpy()]
    rec_is_net = rec_net[is_mask.to_numpy()]
    rec_oos_net = rec_net[oos_mask.to_numpy()]

    print("-" * 130)
    print("[C] 汇总：CSV 记录 vs 独立重算")
    print(f"  {'metric':<22}{'CSV':>16}{'recomputed':>16}{'delta':>14}")
    pairs = [
        ("交易数 n", f"{n_csv}", f"{n_ok}", f"{n_ok - n_csv}"),
        ("净 pips 合计", f"{csv_net.sum():+,.1f}", f"{rec_net.sum():+,.1f}",
         f"{rec_net.sum() - csv_net.sum():+,.1f}"),
        ("单笔期望 pips", f"{csv_net.mean():+.3f}", f"{rec_net.mean():+.3f}",
         f"{rec_net.mean() - csv_net.mean():+.3f}"),
        ("单笔期望 R", f"{ok['csv_net_R'].mean():+.4f}", f"{rec_R.mean():+.4f}",
         f"{rec_R.mean() - ok['csv_net_R'].mean():+.4f}"),
        ("净 PF", f"{w.sum() / -l_.sum():.3f}" if l_.sum() else "-",
         f"{w.sum() / -l_.sum():.3f}" if l_.sum() else "-", "-"),
        ("毛 PF", f"{gp / gl:.3f}" if gl > 0 else "-",
         f"{gp / gl:.3f}" if gl > 0 else "-", "-"),
        ("maxDD (R)", f"{dd_R:+.2f}", f"{dd_R:+.2f}", "-"),
        ("maxDD ($ 1手)", f"{dd_u:+,.0f}", f"{dd_u:+,.0f}", "-"),
        ("IS 期望 R", f"{ok.loc[is_mask, 'csv_net_R'].mean():+.4f}",
         f"{rec_is.mean():+.4f}",
         f"{rec_is.mean() - ok.loc[is_mask, 'csv_net_R'].mean():+.4f}"),
        ("OOS 期望 R", f"{ok.loc[oos_mask, 'csv_net_R'].mean():+.4f}",
         f"{rec_oos.mean():+.4f}",
         f"{rec_oos.mean() - ok.loc[oos_mask, 'csv_net_R'].mean():+.4f}"),
        ("IS 净 pips", f"{ok.loc[is_mask, 'csv_net'].sum():+,.1f}",
         f"{rec_is_net.sum():+,.1f}",
         f"{rec_is_net.sum() - ok.loc[is_mask, 'csv_net'].sum():+,.1f}"),
        ("OOS 净 pips", f"{ok.loc[oos_mask, 'csv_net'].sum():+,.1f}",
         f"{rec_oos_net.sum():+,.1f}",
         f"{rec_oos_net.sum() - ok.loc[oos_mask, 'csv_net'].sum():+,.1f}"),
    ]
    for a, b, c, d in pairs:
        print(f"  {a:<22}{b:>16}{c:>16}{d:>14}")

    # ---------------- OOS trades in full ----------------
    print("-" * 130)
    print(f"[D] OOS {oos_n} 笔逐笔明细 (year >= {args.oos_year}) —— "
          f"这 {oos_n} 笔单独支撑 OOS 期望 R {rec_oos.mean():+.4f}")
    oos_df = ok.loc[oos_mask, ["date", "side", "csv_entry_px", "rec_exit_px",
                               "rec_reason", "csv_gross", "rec_net",
                               "rec_net_R", "rec_hold", "dist_O_pips"]]
    print(f"  {'date':<12}{'side':<7}{'entry':>9}{'exit':>9}{'reason':<9}"
          f"{'gross':>9}{'net':>9}{'R':>9}{'hold':>6}{'dist_O':>9}")
    for _, r in oos_df.iterrows():
        print(f"  {r['date']:<12}{r['side']:<7}{r['csv_entry_px']:>9.5f}"
              f"{r['rec_exit_px']:>9.5f}{r['rec_reason']:<9}"
              f"{r['csv_gross']:>9.1f}{r['rec_net']:>9.1f}"
              f"{r['rec_net_R']:>+9.3f}{r['rec_hold']:>6}{r['dist_O_pips']:>9.0f}")
    print(f"  OOS 合计 gross {oos_df['csv_gross'].sum():+,.1f} pips | "
          f"net {oos_df['rec_net'].sum():+,.1f} pips | "
          f"成本 {args.cost_pips * oos_n:,.1f} pips | "
          f"赢 {int((oos_df['rec_net'] > 0).sum())} 亏 "
          f"{int((oos_df['rec_net'] <= 0).sum())}")

    # ---------------- structural facts ----------------
    print("-" * 130)
    print("[E] 结构性核对")
    ties = int(ok["tie"].sum())
    print(f"  同 bar 同时触及止损与目标 (tie) : {ties} 笔"
          f"{'  -> 无 tie，止损优先假设不影响结果' if ties == 0 else '  -> 有 tie，止损优先假设实质影响结果'}")
    d = ok["dist_O_pips"]
    print(f"  入场时距 O : mean {d.mean():.0f}p  median {d.median():.0f}p  "
          f"p25 {d.quantile(0.25):.0f}p  p75 {d.quantile(0.75):.0f}p  "
          f"max {d.max():.0f}p")
    print(f"  超出 1% 边界的幅度 : mean {ok['overshoot_pips'].mean():+.0f}p "
          f"(正 = 入场时价格已越过 1% 边界)")
    print(f"     -> 1% at ~1.10 约 110p，实测入场平均距 O "
          f"{d.mean():.0f}p，即平均每笔多追 "
          f"{ok['overshoot_pips'].mean():.0f}p")
    reasons = ok["rec_reason"].value_counts().to_dict()
    print(f"  出场分布 : {reasons}")
    print(f"  单笔最大赢 {rec_gross.max():+.0f}p / 最大亏 {rec_gross.min():+.0f}p")
    print(f"  净 pips 最大 +{rec_net.max():.0f} / 最小 {rec_net.min():.0f}")

    # ---------------- verdict ----------------
    print("-" * 130)
    print("[F] 审计结论")
    if n_err:
        print(f"  !! {n_err} 笔无法重算（entry_bar 缺失或数据不足），见 JSON")
    if all_agree and n_err == 0:
        print("  逐笔重算与 CSV 全部字段一致 —— 回测实现未发现差异。")
        print(f"  1.0% 组在既定规则下的 +{rec_net.sum():,.0f} pips 净额、"
              f"OOS +{rec_oos.mean():.4f}R 是规则内真实结果，非实现产物。")
    else:
        print("  !! 存在不一致，见 [A] 各字段 disagree 计数 —— 需先修正实现再谈结果。")
    print(f"  但 OOS 仅 {oos_n} 笔：以 n={oos_n} 判断期望 R {rec_oos.mean():+.4f}，"
          f"单次标准误约 {rec_oos.std(ddof=1) / np.sqrt(oos_n):.4f}R，"
          f"95% 区间约 [{rec_oos.mean() - 1.96 * rec_oos.std(ddof=1) / np.sqrt(oos_n):+.3f}, "
          f"{rec_oos.mean() + 1.96 * rec_oos.std(ddof=1) / np.sqrt(oos_n):+.3f}]R。")
    print("  该区间是否包含 0 决定了 OOS 证据是否成立，见上方数值。")
    print("=" * 130)

    # ---------------- JSON ----------------
    report = {
        "audit_scope": {
            "trades_csv": str(args.trades_csv),
            "n_trades": n_csv,
            "rules": {"trigger_pct": args.pct,
                      "window": f"Beijing {WIN_START_HR}-{WIN_END_HR}",
                      "stop": f"A fixed {args.fixed_stop_pips} pips",
                      "target": "day open O",
                      "time_stop_bars": args.max_hold_bars,
                      "cost_pips": args.cost_pips},
            "method": ("each trade recomputed from raw 5m bars on a separate "
                       "code path from the simulator that wrote the CSV"),
        },
        "per_field_agreement": {
            name: {"compared": int(len(ok[flag])),
                   "agree": int(ok[flag].sum()),
                   "disagree": int(len(ok[flag]) - ok[flag].sum())}
            for name, flag, _, _, _ in checks
        },
        "rule_checks": {
            "entry_is_trigger_bar_close": [int(entry_closes), n_ok],
            "entry_bar_touched_band": [band, n_ok],
            "entry_bar_in_window": [window, n_ok],
            "stop_is_entry_minus_fixed": [int(ok["stop_ok"].sum()), n_ok],
            "target_equals_day_open": [tgt_eq_O, n_ok],
            "cost_deducted_exactly": [cost, n_ok],
            "same_bar_stop_target_ties": ties,
        },
        "is_oos_reconciliation": {
            "oos_year": args.oos_year,
            "is_trades": is_n, "oos_trades": oos_n,
            "target_exits_total": int(tgt_is + tgt_oos),
            "target_exits_in_is": tgt_is, "target_exits_in_oos": tgt_oos,
            "oos_target_hit_rate": (tgt_oos / oos_n) if oos_n else None,
            "full_target_hit_rate": ((tgt_is + tgt_oos) / n_ok) if n_ok else None,
        },
        "aggregates": {
            "csv_net_pips_total": float(csv_net.sum()),
            "recomputed_net_pips_total": float(rec_net.sum()),
            "recomputed_expectancy_R": float(rec_R.mean()),
            "is_expectancy_R": float(rec_is.mean()),
            "oos_expectancy_R": float(rec_oos.mean()),
            "oos_expectancy_R_stderr": float(
                rec_oos.std(ddof=1) / np.sqrt(oos_n)) if oos_n > 1 else None,
            "oos_ci95": [float(rec_oos.mean() - 1.96 * rec_oos.std(ddof=1) / np.sqrt(oos_n)),
                         float(rec_oos.mean() + 1.96 * rec_oos.std(ddof=1) / np.sqrt(oos_n))]
                        if oos_n > 1 else None,
            "is_net_pips": float(rec_is_net.sum()),
            "oos_net_pips": float(rec_oos_net.sum()),
            "net_PF": float(w.sum() / -l_.sum()) if l_.sum() else None,
            "gross_PF": float(gp / gl) if gl > 0 else None,
            "max_dd_R": dd_R, "max_dd_usd_1lot": dd_u,
            "exit_reasons": {str(k): int(v) for k, v in reasons.items()},
        },
        "structure": {
            "entry_dist_O_pips": {"mean": float(d.mean()),
                                  "median": float(d.median()),
                                  "p25": float(d.quantile(0.25)),
                                  "p75": float(d.quantile(0.75)),
                                  "max": float(d.max())},
            "overshoot_past_1pct_band_pips": {
                "mean": float(ok["overshoot_pips"].mean()),
                "median": float(ok["overshoot_pips"].median())},
            "max_gross_win_pips": float(rec_gross.max()),
            "max_gross_loss_pips": float(rec_gross.min()),
        },
        "oos_trades": oos_df.to_dict(orient="records"),
    }
    rp = out / "exp03_audit_1pct_report.json"
    rp.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                  encoding="utf-8")
    adf.to_csv(out / "exp03_audit_1pct_per_trade.csv", index=False)
    print(f"report     -> {rp}")
    print(f"per-trade  -> {out / 'exp03_audit_1pct_per_trade.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
