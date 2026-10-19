#!/usr/bin/env python3
"""EURUSD Breakout Continuation -- Exp04 EVENT STUDY.

Research question
-----------------
Reversal V1 (exp01-03, now frozen) asked: "after a large deviation from the
day open, does price revert?" Exp04 asks the opposite:

    after price breaks the extreme of the prior N completed M5 bars,
    does it keep travelling in the breakout direction?

This is an EVENT STUDY, not a trading strategy. There are no stops, no
targets, no position sizing, no session filter, and no entry filtering
beyond the signal itself. Signals recur inside the same move and their
observation windows overlap, so every signal is NOT an independent
observation. That is measured and reported, and the uncertainty is
estimated with a block bootstrap plus a non-overlapping subsample rather
than a naive std/sqrt(n).

Signal definition
-----------------
    up   breakout : close[i] > max(high[i-12 .. i-1])   (strict >)
    down breakout : close[i] < min(low[i-12 .. i-1])     (strict <)

The signal bar never participates in its own boundary: the extremes come
from rolling(12) over bars [i-12, i-1], i.e. rolling(...).shift(1).

    entry : open  of bar i+1  (the NEXT bar, never the signal close)
    exit  : close of bar i+H  for H in {12, 48}
    return: up   -> (exit - entry) / PIP
            down -> (entry - exit) / PIP
so a positive number always means "price continued in the breakout
direction".

Exclusions (each counted and reported)
--------------------------------------
  1. position : bar i+H must exist (no partial window at series end)
  2. lookback : window [i-12, i] must contain no time gap
  3. holding  : window [i, i+H] must contain no time gap
A "time gap" is any step between consecutive M5 bars that is not exactly
5 minutes. The data has a genuine ~48h gap every weekend plus occasional
missing minutes; a window spanning a gap is not really "1 hour" or
"4 hours" of market time, so it is dropped rather than silently absorbed.

Fixed by design -- NOT scanned
------------------------------
lookback = 12 bars, horizons = {12, 48} bars, cost = 1.5 pips round trip.
The script exposes these as CLI flags only so a run can be reproduced or
an explicit alternative requested. It never sweeps them, and a
disappointing result is never used as a reason to change them here.

Reuses, modifies nothing
------------------------
load_m5 / timezone constants from eurusd_reversal_v1_m5.py, and the
IS/OOS split already used by exp01-exp03 (year < 2016 = IS, >= 2016 = OOS).
Nothing in Reversal V1, exp01, exp02, exp03 or the raw parquet is touched.
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
from eurusd_reversal_v1_m5 import load_m5, PIP, STORED_TO_BEIJING   # noqa: E402

REPO = Path(__file__).resolve().parents[2]
DEFAULT_M1 = REPO / "artifacts/histdata_v9/parsed/eurusd_2000-2026_bars.parquet"
DEFAULT_OUT = REPO / "artifacts/research/eurusd_breakout"

LOOKBACK = 12               # boundary = prior 12 COMPLETED M5 bars
HORIZONS = (12, 48)         # 1 hour, 4 hours
COST_PIPS = 1.5             # assumed round trip, same as exp01-exp03
OOS_YEAR = 2016             # same split as exp01-exp03
BAR_MIN = 5
N_BOOT = 2000
SEED = 20240416
H_LABEL = {12: "1h", 48: "4h"}


# ----------------------------------------------------------------------
def build_events(m5: pd.DataFrame, lookback: int, horizons: tuple):
    """Return (events DataFrame, exclusion ledger).

    All heavy work is vectorised. No future data is read when deciding
    whether a signal exists or where the entry is.
    """
    n = len(m5)
    ts = m5.index
    o = m5["open"].to_numpy(float)
    h = m5["high"].to_numpy(float)
    lo = m5["low"].to_numpy(float)
    c = m5["close"].to_numpy(float)

    # extremes of the prior `lookback` COMPLETED bars; current bar excluded.
    # NaN comparisons are False, so the first `lookback` bars produce no signal.
    prior_hi = pd.Series(h).rolling(lookback).max().shift(1).to_numpy()
    prior_lo = pd.Series(lo).rolling(lookback).min().shift(1).to_numpy()

    # time gaps: any step that is not exactly BAR_MIN minutes.
    # gcum[k] = number of gaps strictly before bar k  (len = n + 1)
    step = np.diff(ts.values).astype("timedelta64[m]").astype(int)
    gap = np.zeros(n, dtype=np.int64)
    gap[:-1] = (step != BAR_MIN).astype(np.int64)
    gcum = np.concatenate([[0], np.cumsum(gap)])

    up_idx = np.flatnonzero(c > prior_hi)
    dn_idx = np.flatnonzero(c < prior_lo)

    ledger = {
        "lookback_bars": int(lookback),
        "total_signals_considered": int(len(up_idx) + len(dn_idx)),
        "up_raw": int(len(up_idx)), "down_raw": int(len(dn_idx)),
        "bars": int(n),
        "gap_bars_total": int(gap.sum()),
    }

    parts = []
    for direction, idx in (("up", up_idx), ("down", dn_idx)):
        if len(idx) == 0:
            continue
        # (2) lookback window continuity: bars [i-lookback .. i]
        lb_clean = (gcum[idx] - gcum[idx - lookback]) == 0
        entry = o[np.minimum(idx + 1, n - 1)]

        rec = {"entry": entry, "lb_clean": lb_clean}
        for H in horizons:
            # (1) position available
            pos_ok = (idx + H) < n
            # (3) holding window continuity: bars [i .. i+H]
            hold_clean = (gcum[np.minimum(idx + H, n)] - gcum[idx]) == 0
            iH = np.minimum(idx + H, n - 1)
            exit_px = c[iH]
            r = ((exit_px - entry) / PIP if direction == "up"
                 else (entry - exit_px) / PIP)
            rec[f"r{H}"] = r
            rec[f"x{H}"] = exit_px
            rec[f"ok{H}"] = lb_clean & pos_ok & hold_clean
            # staged counts so each exclusion reason is visible separately
            ledger.setdefault(f"H{H}", {})[direction] = {
                "raw": int(len(idx)),
                "after_lookback_gap": int((lb_clean & np.ones(len(idx), bool)).sum()),
                "after_position": int((lb_clean & pos_ok).sum()),
                "after_holding_gap": int((lb_clean & pos_ok & hold_clean).sum()),
                "dropped_lookback_gap": int((~lb_clean).sum()),
                "dropped_position": int((lb_clean & ~pos_ok).sum()),
                "dropped_holding_gap": int((lb_clean & pos_ok & ~hold_clean).sum()),
            }

        d = pd.DataFrame({
            "bar_i": idx,
            "signal_bar": ts[idx].strftime("%Y-%m-%d %H:%M:%S"),
            "date": ts[idx].strftime("%Y-%m-%d"),
            "year": ts[idx].year,
            "direction": direction,
            "signal_close": c[idx],
            "prior_high": prior_hi[idx],
            "prior_low": prior_lo[idx],
            "entry_bar": ts[np.minimum(idx + 1, n - 1)].strftime("%Y-%m-%d %H:%M:%S"),
            "entry_px": entry,
            "valid_lookback": lb_clean,
        })
        for H in horizons:
            d[f"ret_{H}"] = np.where(rec[f"ok{H}"], rec[f"r{H}"], np.nan)
            d[f"exit_{H}_px"] = np.where(rec[f"ok{H}"], rec[f"x{H}"], np.nan)
            d[f"valid_{H}"] = rec[f"ok{H}"]
        parts.append(d)

    edf = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    if len(edf):
        edf = edf.sort_values("signal_bar").reset_index(drop=True)
    return edf, ledger


# ----------------------------------------------------------------------
def stats(r, cost=COST_PIPS):
    """Toplevel distribution stats for one set of directional returns."""
    r = np.asarray(r, float)
    r = r[np.isfinite(r)]
    n = len(r)
    if n == 0:
        return {"n": 0}
    net = r - cost
    sd = float(r.std(ddof=1)) if n > 1 else None
    se = sd / np.sqrt(n) if sd is not None else None
    return {
        "n": int(n),
        "mean_pips": round(float(r.mean()), 4),
        "median_pips": round(float(np.median(r)), 4),
        "std_pips": round(sd, 4) if sd is not None else None,
        "pos_share": round(float((r > 0).mean()), 4),
        "mean_net_pips": round(float(net.mean()), 4),
        "pos_share_net": round(float((net > 0).mean()), 4),
        "total_pips": round(float(r.sum()), 1),
        "total_net_pips": round(float(net.sum()), 1),
        "naive_se": round(se, 4) if se is not None else None,
        "naive_ci95": ([round(float(r.mean()) - 1.96 * se, 4),
                        round(float(r.mean()) + 1.96 * se, 4)]
                       if se is not None else None),
    }


def block_bootstrap(r, dates, n_boot=N_BOOT, seed=SEED):
    """Calendar-month block bootstrap. Handles time clustering: overlapping
    signals inside a month are resampled together, so the CI reflects
    dependence rather than pretending each signal is independent."""
    r = np.asarray(r, float)
    r = r[np.isfinite(r)]
    if len(r) < 2:
        return None
    ym = pd.Series(r).groupby(pd.Index(dates).str[:7])
    sums = ym.sum().to_numpy(float)
    counts = ym.size().to_numpy(float)
    nb = len(sums)
    if nb < 2:
        return None
    rng = np.random.default_rng(seed)
    means = np.empty(n_boot)
    for b in range(n_boot):
        pick = rng.integers(0, nb, nb)
        means[b] = sums[pick].sum() / counts[pick].sum()
    lo, hi = np.percentile(means, [2.5, 97.5])
    return {
        "method": "calendar-month block bootstrap",
        "n_month_blocks": int(nb), "n_boot": int(n_boot), "seed": int(seed),
        "mean_ci95": [round(float(lo), 4), round(float(hi), 4)],
        "boot_se": round(float(means.std(ddof=1)), 4),
    }


def nonoverlap_mask(idx_sorted, H):
    """Greedy non-overlapping selection: keep the earliest signal, then skip
    every signal whose observation window [i, i+H] overlaps it."""
    m = np.zeros(len(idx_sorted), dtype=bool)
    last_end = -1 << 62
    for k, i in enumerate(idx_sorted):
        if i > last_end:
            m[k] = True
            last_end = i + H
    return m


def concentration(yearly, key_mean, key_n):
    """Year-level concentration. When the total is negative a plain
    share-of-total flips sign and means nothing, so shares are taken over
    the SUM OF ABSOLUTE yearly contributions and the worst year is reported
    alongside the best one."""
    y = yearly.dropna(subset=[key_mean])
    if len(y) == 0:
        return None
    contrib = y[key_mean] * y[key_n]
    tot = float(contrib.sum())
    absum = float(contrib.abs().sum())
    order = contrib.sort_values(ascending=False)
    top1 = float(order.iloc[0])
    top3 = float(order.iloc[:3].sum())
    bot1 = float(order.iloc[-1])
    return {
        "years_counted": int(len(y)),
        "years_positive": int((contrib > 0).sum()),
        "years_negative": int((contrib < 0).sum()),
        "total_pips": round(tot, 1),
        "best_year": int(order.index[0]),
        "best_year_pips": round(top1, 1),
        "worst_year": int(order.index[-1]),
        "worst_year_pips": round(bot1, 1),
        "best_year_abs_share": round(top1 / absum, 4) if absum else None,
        "top3_abs_share": round(top3 / absum, 4) if absum else None,
        "ex_best_year_pips": round(tot - top1, 1),
        "ex_worst_year_pips": round(tot - bot1, 1),
    }


# ----------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(
        description="Exp04 EURUSD breakout-continuation event study")
    ap.add_argument("--m1", default=str(DEFAULT_M1))
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT))
    ap.add_argument("--lookback", type=int, default=LOOKBACK)
    ap.add_argument("--horizons", default="12,48")
    ap.add_argument("--cost-pips", type=float, default=COST_PIPS)
    ap.add_argument("--oos-year", type=int, default=OOS_YEAR)
    args = ap.parse_args()
    horizons = tuple(int(x) for x in args.horizons.split(","))

    m5, quality = load_m5(Path(args.m1))
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    print("=" * 128)
    print("Exp04 — EURUSD Breakout Continuation — EVENT STUDY (not a strategy)")
    print("=" * 128)
    print(f"data       : {quality['m5_bars']:,} M5 bars  "
          f"{quality['m5_range'][0]} .. {quality['m5_range'][1]}")
    print(f"timezone   : stored EST(UTC-5), Beijing = stored + {STORED_TO_BEIJING}h "
          f"(fixed, no DST) — reused from eurusd_reversal_v1_m5.load_m5")
    print(f"lookback   : {args.lookback} completed M5 bars (signal bar excluded)")
    print(f"horizons   : {', '.join(f'{H_LABEL.get(H,H)} = {H} bars' for H in horizons)}")
    print(f"entry/exit : open of NEXT bar -> close of bar i+H  (no signal-bar fill)")
    print(f"cost       : {args.cost_pips} pips round trip (ASSUMED)")
    print(f"IS/OOS     : IS year < {args.oos_year}, OOS year >= {args.oos_year} "
          f"(split reused from exp01-exp03)")

    edf, ledger = build_events(m5, args.lookback, horizons)
    csv_path = out / "exp04_events.csv"
    edf.to_csv(csv_path, index=False, float_format="%.5f")

    # ---------------- head: signal counts and exclusions ----------------
    print("-" * 128)
    print("[A] 信号数量与筛选（排除理由分别计数）")
    print(f"  M5 bars {ledger['bars']:,} | 非 5 分钟的时间断点 {ledger['gap_bars_total']:,} 处"
          f"（周末休市 + 缺失分钟）")
    print(f"  原始信号：向上 {ledger['up_raw']:,}  向下 {ledger['down_raw']:,}  "
          f"合计 {ledger['total_signals_considered']:,}")
    for H in horizons:
        print(f"  --- horizon {H_LABEL.get(H, H)} ({H} bars) ---")
        print(f"    {'dir':<6}{'raw':>9}{'去掉前视断点':>14}{'去掉位置不足':>14}"
              f"{'去掉持仓断点':>14}{'有效':>9}")
        for dd in ("up", "down"):
            e = ledger[f"H{H}"][dd]
            print(f"    {dd:<6}{e['raw']:>9}{e['dropped_lookback_gap']:>14}"
                  f"{e['dropped_position']:>14}{e['dropped_holding_gap']:>14}"
                  f"{e['after_holding_gap']:>9}")

    # ---------------- [B] full sample ----------------
    def cell(v, w=9, f="{:+.3f}"):
        return f"{f.format(v):>{w}}" if v is not None else f"{'-':>{w}}"

    print("-" * 128)
    print("[B] 全样本方向性收益（正 = 沿突破方向继续运行）")
    print(f"  {'dir':<6}{'horizon':<8}{'n':>9}{'均值p':>10}{'中位p':>10}"
          f"{'标准差':>10}{'正向%':>9}{'净值均值p':>11}{'净值正向%':>11}{'净总额p':>12}")
    full = {}
    for H in horizons:
        for dd in ("up", "down"):
            sub = edf[(edf["direction"] == dd) & edf[f"valid_{H}"]]
            r = sub[f"ret_{H}"].to_numpy(float)
            s = stats(r, args.cost_pips)
            full[(dd, H)] = s
            tot = s.get("total_net_pips")
            tot_s = f"{tot:+,.0f}" if tot is not None else "-"
            print(f"  {dd:<6}{H_LABEL.get(H, str(H)):<8}{s.get('n', 0):>9}"
                  f"{cell(s.get('mean_pips')):>10}{cell(s.get('median_pips')):>10}"
                  f"{cell(s.get('std_pips')):>10}"
                  f"{s.get('pos_share', 0):>9.1%}"
                  f"{cell(s.get('mean_net_pips')):>11}"
                  f"{s.get('pos_share_net', 0):>11.1%}"
                  f"{tot_s:>12}")

    # ---------------- [C] overlap ----------------
    print("-" * 128)
    print("[C] 信号重叠与观察窗口重叠")
    for H in horizons:
        for dd in ("up", "down"):
            sub = edf[(edf["direction"] == dd) & edf[f"valid_{H}"]]
            if len(sub) == 0:
                continue
            # overlap is measured in REAL TIME: bar_i is the position in the
            # M5 series, and the event frame is time-sorted so it is ascending.
            # (Row numbers in the event frame are NOT bar positions, because
            # up and down signals interleave.)
            barpos = sub["bar_i"].to_numpy()
            m = nonoverlap_mask(barpos, H)
            n_non = int(m.sum())
            n_tot = len(barpos)
            r_all = sub[f"ret_{H}"].to_numpy(float)
            r_non = r_all[m]
            print(f"  {H_LABEL.get(H, str(H)):<4}{dd:<6} 信号 {n_tot:>6}  "
                  f"互不重叠子集 {n_non:>6} ({n_non / n_tot:>5.1%})  "
                  f"重叠率 {1 - n_non / n_tot:>5.1%}")
            print(f"       全样本 均值 {r_all.mean():+.4f}p | "
                  f"非重叠子集 均值 {r_non.mean():+.4f}p "
                  f"(n={n_non}, 净值 {r_non.mean() - args.cost_pips:+.4f}p)")

    # ---------------- [D] uncertainty ----------------
    print("-" * 128)
    print("[D] 统计不确定性（朴素 SE 会低估，因信号重叠）")
    print(f"  {'dir':<6}{'horizon':<8}{'n':>9}{'均值p':>10}{'朴素SE':>9}"
          f"{'朴素95%CI':>20}{'块自助95%CI':>22}{'非重叠n':>9}{'非重叠均值':>11}")
    unc = {}
    for H in horizons:
        for dd in ("up", "down"):
            sub = edf[(edf["direction"] == dd) & edf[f"valid_{H}"]]
            r = sub[f"ret_{H}"].to_numpy(float)
            r = r[np.isfinite(r)]
            if len(r) == 0:
                continue
            s = stats(r, args.cost_pips)
            bb = block_bootstrap(r, sub["date"].to_numpy())
            barpos = sub["bar_i"].to_numpy()
            m = nonoverlap_mask(barpos, H)
            r_non = r[m] if len(r) == len(barpos) else None
            unc[(dd, H)] = {"stats": s, "block_bootstrap": bb,
                            "nonoverlap": {
                                "n": int(m.sum()),
                                "mean_pips": (round(float(r_non.mean()), 4)
                                              if r_non is not None and len(r_non)
                                              else None),
                                "mean_net_pips": (
                                    round(float(r_non.mean() - args.cost_pips), 4)
                                    if r_non is not None and len(r_non) else None),
                            }}
            naive = (f"[{s['naive_ci95'][0]:+.3f},{s['naive_ci95'][1]:+.3f}]"
                     if s.get("naive_ci95") else "-")
            bbs = (f"[{bb['mean_ci95'][0]:+.3f},{bb['mean_ci95'][1]:+.3f}]"
                   if bb else "-")
            non_mean = (f"{r_non.mean():+.4f}" if r_non is not None and len(r_non)
                        else "-")
            print(f"  {dd:<6}{H_LABEL.get(H, str(H)):<8}{s['n']:>9}"
                  f"{s['mean_pips']:>+10.4f}{s['naive_se']:>9.4f}"
                  f"{naive:>20}{bbs:>22}"
                  f"{(int(m.sum()) if r_non is not None else 0):>9}{non_mean:>11}")

    # ---------------- [E] IS / OOS ----------------
    print("-" * 128)
    print(f"[E] IS (<{args.oos_year}) vs OOS (>={args.oos_year})")
    print(f"  {'dir':<6}{'horizon':<8}{'phase':<6}{'n':>8}{'均值p':>10}"
          f"{'正向%':>9}{'净值均值p':>11}{'净总额p':>12}")
    is_oos = {}
    for H in horizons:
        for dd in ("up", "down"):
            for ph, mask in (("IS", edf["year"] < args.oos_year),
                             ("OOS", edf["year"] >= args.oos_year)):
                sub = edf[(edf["direction"] == dd) & edf[f"valid_{H}"] & mask]
                r = sub[f"ret_{H}"].to_numpy(float)
                s = stats(r, args.cost_pips)
                is_oos[(dd, H, ph)] = s
                if s.get("n", 0) == 0:
                    print(f"  {dd:<6}{H_LABEL.get(H, str(H)):<8}{ph:<6}{0:>8}"
                          f"{'-':>10}{'-':>9}{'-':>11}{'-':>12}")
                    continue
                print(f"  {dd:<6}{H_LABEL.get(H, str(H)):<8}{ph:<6}{s['n']:>8}"
                      f"{s['mean_pips']:>+10.4f}{s['pos_share']:>9.1%}"
                      f"{s['mean_net_pips']:>+11.4f}"
                      f"{s['total_net_pips']:>+12,.0f}")

    # ---------------- [F] yearly ----------------
    print("-" * 128)
    print("[F] 年度分布（向上 + 向下合并，净值 = 扣 1.5p 后）")
    yearly_all = {}
    for H in horizons:
        sub = edf[edf[f"valid_{H}"]]
        y = sub.groupby("year")[f"ret_{H}"].agg(n="size", mean="mean", sum="sum")
        y["mean_net"] = y["mean"] - args.cost_pips
        yearly_all[H] = y
        print(f"  --- {H_LABEL.get(H, str(H))} ({H} bars) ---")
        print(f"    {'year':<6}{'n':>8}{'均值p':>10}{'净值均值p':>11}{'总额p':>11}"
              f"{'正向%':>9}")
        for yr, row in y.iterrows():
            sub_y = sub[sub["year"] == yr][f"ret_{H}"]
            print(f"    {yr:<6}{int(row['n']):>8}{row['mean']:>+10.4f}"
                  f"{row['mean_net']:>+11.4f}{row['sum']:>+11,.0f}"
                  f"{(sub_y > 0).mean():>9.1%}")
        cc = concentration(y.reset_index(), "mean", "n")
        if cc:
            print(f"    集中度：正收益 {cc['years_positive']}/{cc['years_counted']} 年 | "
                  f"最好年 {cc['best_year']} {cc['best_year_pips']:+,.0f}p | "
                  f"最差年 {cc['worst_year']} {cc['worst_year_pips']:+,.0f}p | "
                  f"剔除最差年后 {cc['ex_worst_year_pips']:+,.0f}p")

    # ---------------- [G] concentration per direction ----------------
    print("-" * 128)
    print("[G] 收益集中度（分方向）")
    print(f"  {'dir':<6}{'horizon':<8}{'正年数':>8}{'负年数':>8}{'最好年':>8}"
          f"{'最好年p':>10}{'最差年':>8}{'最差年p':>10}{'剔除最差年后p':>14}")
    conc = {}
    for H in horizons:
        for dd in ("up", "down"):
            sub = edf[(edf["direction"] == dd) & edf[f"valid_{H}"]]
            if len(sub) == 0:
                continue
            y = sub.groupby("year")[f"ret_{H}"].agg(n="size", mean="mean")
            cc = concentration(y.reset_index(), "mean", "n")
            if not cc:
                continue
            conc[(dd, H)] = cc
            print(f"  {dd:<6}{H_LABEL.get(H, str(H)):<8}{cc['years_positive']:>8}"
                  f"{cc['years_negative']:>8}{cc['best_year']:>8}"
                  f"{cc['best_year_pips']:>+10,.0f}{cc['worst_year']:>8}"
                  f"{cc['worst_year_pips']:>+10,.0f}"
                  f"{cc['ex_worst_year_pips']:>+14,.0f}")

    # ---------------- [H] verdict scaffold ----------------
    print("-" * 128)
    print("[H] 性质声明")
    print("  * 这是事件研究：无止损、无止盈、无仓位管理、无时段过滤、无信号过滤。")
    print("  * 信号在同一段行情内反复出现，观察窗口重叠 —— 见 [C]。")
    print("  * 因此 [D] 的朴素 SE 低估真实不确定性，以块自助 CI 为准。")
    print("  * 即使方向性成立，也不等于存在可交易策略：还需入场、止损、退出、")
    print("    成本与容量研究，且本研究的收益未扣除点差之外的滑点与库存成本。")

    # ---------------- JSON ----------------
    def pack(d):
        return {f"{a}|{b}": v for (a, b), v in d.items()}

    report = {
        "study": {
            "name": "EXP04 EURUSD breakout continuation",
            "type": "event study, NOT a trading strategy",
            "question": ("after close breaks the prior 12 completed M5 bars' "
                         "extreme, does price continue in that direction?"),
        },
        "data": {
            "source_m1": str(args.m1),
            **quality,
            "timezone": (f"stored EST(UTC-5) fixed; Beijing = stored + "
                         f"{STORED_TO_BEIJING}h; no DST, verified off the FX "
                         f"calendar in exp01/eurusd_m1_audit.py"),
            "missing_data_policy": (
                "M1 -> M5 resample drops empty 5-minute buckets (.dropna()); "
                "any step between consecutive M5 bars that is not exactly 5 "
                "minutes is treated as a time gap. Events whose lookback "
                "window or holding window spans a gap are excluded and counted."),
            "is_oos_split": {"is": f"year < {args.oos_year}",
                             "oos": f"year >= {args.oos_year}",
                             "source": "reused from exp01-exp03"},
        },
        "signal_definition": {
            "up_breakout": "close[i] > max(high[i-12 .. i-1])  (strict)",
            "down_breakout": "close[i] < min(low[i-12 .. i-1])  (strict)",
            "current_bar_in_boundary": False,
            "entry": "open of bar i+1 (next bar, never the signal close)",
            "exit": "close of bar i+H",
            "directional_return_up": "(exit - entry) / PIP",
            "directional_return_down": "(entry - exit) / PIP",
            "positive_means": "price continued in the breakout direction",
            "lookahead": "none — signal and entry use bars <= i+1 only",
        },
        "fixed_parameters": {
            "lookback_bars": args.lookback,
            "horizon_bars": list(horizons),
            "cost_pips_rt": args.cost_pips,
            "note": ("fixed by design; the script never sweeps them and a poor "
                     "result is not used here to change them"),
        },
        "signal_counts_and_exclusions": ledger,
        "full_sample": pack(full),
        "uncertainty": pack(unc),
        "is_oos": {f"{a}|{b}|{c}": v for (a, b, c), v in is_oos.items()},
        "concentration": pack(conc),
    }
    rp = out / "exp04_report.json"
    rp.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                  encoding="utf-8")

    print("=" * 128)
    print(f"events -> {csv_path}")
    print(f"report -> {rp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
