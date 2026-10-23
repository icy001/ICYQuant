#!/usr/bin/env python3
"""Exp09 -- Chan (Chanlun / 缠论) third-type buy & sell points, as an event study.

ASKED FOR BY THE USER, BUT PRICED AND SAMPLED HONESTLY
------------------------------------------------------
This is an event study, not a strategy. The question is narrow: after a
Chan "third-type" point is confirmed, does price continue in the implied
direction by more than the execution cost?

Confirmed execution terms: 5 USD per lot per side.
    EURUSD: 1 pip on 1 lot = 100,000 * 0.0001 = 10 USD
    -> round trip = 2 * 5 / 10 = 1.0 pip.   (Exp08: M5 reversal dies at 1.0p,
       Sharpe -1.94 / -2.05.)

WHICH CHAN, AND WHY IT IS HARD TO BACKTEST
------------------------------------------
Chan has no single canonical specification. Two problems dominate:

  LOOK-AHEAD. Most Chan structures are only complete in hindsight. A fenxing
  needs the third bar; a bi needs the next fenxing; a zhongshu needs three
  completed bi; a beichi compares two legs and the second one is unfinished
  until it is over. Any backtest that silently uses the completed structure
  is cheating, and that is where the famous "90% win rate Chan backtests"
  come from. Here every structure carries an explicit CONFIRM index and the
  entry is the open of the bar AFTER confirmation.

  DEFINITION CHOICE. Old-bi vs new-bi, feature-sequence vs alternative
  duan-splitting, MACD-area vs force beichi. A negative result below may be a
  property of the chosen definition, not of Chan. The definition is fixed in
  advance and no variant is scanned.

THE FORMALISATION USED HERE
---------------------------
  1. Containment merge (K-line 包含处理), direction-aware.
  2. Fenxing (顶/底分型) on the merged bars; confirmed at bar j+1.
  3. New-bi (新笔): opposite fenxing at least MIN_GAP merged bars apart.
  4. Zhongshu (中枢): overlap of three consecutive bi; ZG/ZD = overlap
     bounds. Rejected when ZD >= ZG.
  5. Third-type point (第三类买卖点), as a state machine that is fully
     decidable online:
         break out of the zhongshu,
         pull back WITHOUT re-entering it,
         then break out again in the same direction -> confirmed.
     Third-type BUY: break above ZG, pull back with low > ZG, then close
     above the pre-pullback peak.
     Third-type SELL: mirror image.
  No beichi and no duan are used, precisely because they are the parts that
  cannot be decided without hindsight.

Entry is open[i+1]. Signal and entry use only bars <= i.

Scales: D1 (aggregated from M1 with the platform FX day convention) and M5.
They are both reported because the binding constraint differs: at D1 the
1.0 pip cost is negligible against the move but samples are small, while at
M5 samples are large but Exp08 already showed 1.0 pip kills that scale.
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
from eurusd_reversal_v1_m5 import load_m5, PIP, STORED_TO_BEIJING          # noqa: E402
from exp05_breakout_continuation_longer_horizon import (                   # noqa: E402
    load_m1_bj, aggregate_to, FX_DAY_START, DEFAULT_M1 as DEFAULT_M1_PARQUET)
from exp04_breakout_continuation import (                                  # noqa: E402
    stats, block_bootstrap, nonoverlap_mask, concentration,
    OOS_YEAR, N_BOOT, SEED)

REPO = Path(__file__).resolve().parents[2]
DEFAULT_OUT = REPO / "artifacts/research/eurusd_chan"

COST_PIPS = 1.0          # 5 USD per lot per side, EURUSD: 1 pip = 10 USD/lot
MIN_GAP = 4              # new-bi: >= 1 independent bar between two fenxing
MAX_WAIT = 200           # bars searched after a zhongshu before it is abandoned
HORIZONS = (5, 10, 20)   # forward bars held
MIN_N_FOR_VERDICT = 200
W = 128


# ----------------------------------------------------------------------
# Chan structures
# ----------------------------------------------------------------------
def merge_contained(high: np.ndarray, low: np.ndarray):
    """K-line containment merge. Returns merged bars and, for each merged bar,
    the ORIGINAL index of the last bar folded into it (its availability time)."""
    ph = [float(high[0])]
    pl = [float(low[0])]
    oidx = [0]
    direction = 1 if high[1] > high[0] else -1
    for i in range(1, len(high)):
        h, l = float(high[i]), float(low[i])
        contained = (h <= ph[-1] and l >= pl[-1]) or (h >= ph[-1] and l <= pl[-1])
        if contained:
            if direction > 0:
                ph[-1] = max(ph[-1], h)
                pl[-1] = max(pl[-1], l)
            else:
                ph[-1] = min(ph[-1], h)
                pl[-1] = min(pl[-1], l)
            oidx[-1] = i
        else:
            ph.append(h)
            pl.append(l)
            oidx.append(i)
        if len(ph) >= 2:
            if ph[-1] > ph[-2]:
                direction = 1
            elif ph[-1] < ph[-2]:
                direction = -1
    return np.array(ph), np.array(pl), np.array(oidx)


def find_fenxing(ph: np.ndarray, pl: np.ndarray, oidx: np.ndarray):
    """(merged_index, type, confirm_original_index). type 1 = top, -1 = bottom.
    A fenxing is only known once the third bar exists, hence confirm at j+1."""
    fx = []
    for j in range(1, len(ph) - 1):
        if ph[j] > ph[j - 1] and ph[j] > ph[j + 1] \
                and pl[j] > pl[j - 1] and pl[j] > pl[j + 1]:
            fx.append((j, 1, int(oidx[j + 1])))
        elif ph[j] < ph[j - 1] and ph[j] < ph[j + 1] \
                and pl[j] < pl[j - 1] and pl[j] < pl[j + 1]:
            fx.append((j, -1, int(oidx[j + 1])))
    return fx


def find_bi(fx, ph, pl, min_gap: int = MIN_GAP):
    """New-bi: from one fenxing to the next opposite one at least min_gap
    merged bars away. Returns (start_pidx, end_pidx, start_type, confirm_orig)."""
    if len(fx) < 2:
        return []
    bi = []
    cur = fx[0]
    k = 1
    while k < len(fx):
        nx = fx[k]
        if nx[1] == cur[1]:
            if (nx[1] == 1 and ph[nx[0]] > ph[cur[0]]) or \
               (nx[1] == -1 and pl[nx[0]] < pl[cur[0]]):
                cur = nx
            k += 1
            continue
        if nx[0] - cur[0] >= min_gap:
            bi.append((cur[0], nx[0], cur[1], nx[2]))
            cur = nx
        k += 1
    return bi


def stroke_range(b, ph, pl):
    s, e, t, _ = b
    if t == -1:          # bottom -> top: rising stroke
        return (float(pl[s]), float(ph[e]))
    return (float(pl[e]), float(ph[s]))


def find_zhongshu(bi, ph, pl):
    """Overlap of three consecutive strokes. Returns (ZD, ZG, confirm_orig)."""
    zs = []
    for i in range(len(bi) - 2):
        r1 = stroke_range(bi[i], ph, pl)
        r2 = stroke_range(bi[i + 1], ph, pl)
        r3 = stroke_range(bi[i + 2], ph, pl)
        zg = min(r1[1], r2[1], r3[1])
        zd = max(r1[0], r2[0], r3[0])
        if zd < zg:
            zs.append((zd, zg, bi[i + 2][3]))
    return zs


def find_third_points(h, l, c, zs, max_wait: int = MAX_WAIT):
    """Third-type buy/sell, decided online.

    buy : break above ZG -> pull back with every low still above ZG -> close
          above the pre-pullback peak.
    sell: mirror image.
    Any return INTO the zhongshu aborts that candidate. Returns
    (kind, confirm_index)."""
    sig = []
    n = len(c)
    for zd, zg, E in zs:
        if E >= n - 2:
            continue
        hi = min(n - 1, E + max_wait)
        # ---- third-type buy
        state, peak = 0, None
        for i in range(E + 1, hi + 1):
            if state == 0:
                if h[i] > zg:
                    state, peak = 1, h[i]
            elif state == 1:
                if l[i] < zg:
                    break
                if h[i] > peak:
                    peak = h[i]
                elif l[i] < peak:
                    state = 2
            elif state == 2:
                if l[i] < zg:
                    break
                if c[i] > peak:
                    sig.append(("buy", i))
                    break
        # ---- third-type sell
        state, trough = 0, None
        for i in range(E + 1, hi + 1):
            if state == 0:
                if l[i] < zd:
                    state, trough = 1, l[i]
            elif state == 1:
                if h[i] > zd:
                    break
                if l[i] < trough:
                    trough = l[i]
                elif h[i] > trough:
                    state = 2
            elif state == 2:
                if h[i] > zd:
                    break
                if c[i] < trough:
                    sig.append(("sell", i))
                    break
    return sig


def chan_signals(bars: pd.DataFrame):
    """Full pipeline. Returns a DataFrame of confirmed signals."""
    h = bars["high"].to_numpy(float)
    lo = bars["low"].to_numpy(float)
    c = bars["close"].to_numpy(float)
    o = bars["open"].to_numpy(float)
    ph, pl, oidx = merge_contained(h, lo)
    fx = find_fenxing(ph, pl, oidx)
    bi = find_bi(fx, ph, pl)
    zs = find_zhongshu(bi, ph, pl)
    sig = find_third_points(h, lo, c, zs)
    rows = []
    for kind, i in sig:
        if i + 1 >= len(o):
            continue
        entry = float(o[i + 1])
        rows.append({"kind": kind, "sig_i": i,
                     "sig_bar": bars.index[i], "entry_bar": bars.index[i + 1],
                     "entry_px": entry})
    edf = pd.DataFrame(rows)
    return edf, {"merged_bars": len(ph), "fenxing": len(fx),
                 "bi": len(bi), "zhongshu": len(zs), "signals": len(edf)}


# ----------------------------------------------------------------------
def build_events(edf: pd.DataFrame, bars: pd.DataFrame, horizons=HORIZONS):
    """Attach forward returns signed so positive = continued in signal
    direction. Entry is open[sig_i+1]; exit is close[sig_i+1+H]."""
    o = bars["open"].to_numpy(float)
    c = bars["close"].to_numpy(float)
    n = len(bars)
    for H in horizons:
        ret = np.full(len(edf), np.nan)
        exit_px = np.full(len(edf), np.nan)
        valid = np.zeros(len(edf), dtype=bool)
        for k, i in enumerate(edf["sig_i"].to_numpy()):
            j = i + 1 + H
            if j < n:
                e = edf["entry_px"].iloc[k]
                x = c[j]
                r = (x - e) / PIP if edf["kind"].iloc[k] == "buy" \
                    else (e - x) / PIP
                ret[k] = r
                exit_px[k] = x
                valid[k] = True
        edf["ret_" + str(H)] = ret
        edf["exit_" + str(H) + "_px"] = exit_px
        edf["valid_" + str(H)] = valid
    return edf


def analyze(edf: pd.DataFrame, scale: str, H: int, years: float) -> dict:
    out = {}
    for kind in ("buy", "sell"):
        s = edf[(edf["kind"] == kind) & edf["valid_" + str(H)]].dropna(
            subset=["ret_" + str(H)])
        if len(s) < 10:
            continue
        r = s["ret_" + str(H)].to_numpy(float)
        st = stats(r, cost=COST_PIPS)
        st["trades_per_year"] = round(len(r) / years, 1)
        bs = block_bootstrap(r, s["entry_bar"].astype(str).to_numpy())
        st["block_ci95"] = bs
        idx = s["sig_i"].to_numpy()
        order = np.argsort(idx, kind="stable")
        mask = nonoverlap_mask(idx[order], H)
        if mask.any():
            rn = r[order][mask]
            st["nonoverlap"] = {"n": int(mask.sum()),
                                "mean": round(float(rn.mean()), 3),
                                "net": round(float(rn.mean() - COST_PIPS), 3)}
        year = pd.to_datetime(s["entry_bar"]).dt.year
        yr = pd.DataFrame({"y": year.to_numpy(), "r": r}).groupby("y")["r"].agg(
            ["mean", "size"])
        yr = yr.rename(columns={"mean": "m", "size": "n"})
        st["concentration"] = concentration(
            yr.reset_index().rename(columns={"y": "year"}), "m", "n")
        st["is_mean"] = round(float(r[year.to_numpy() < OOS_YEAR].mean()), 3) \
            if (year.to_numpy() < OOS_YEAR).any() else None
        st["oos_mean"] = round(float(r[year.to_numpy() >= OOS_YEAR].mean()), 3) \
            if (year.to_numpy() >= OOS_YEAR).any() else None
        out[kind] = st
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Exp09 Chan third-type points")
    ap.add_argument("--m1", default=str(DEFAULT_M1_PARQUET))
    ap.add_argument("--scales", default="D1,M5")
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT))
    args = ap.parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * W)
    print("Exp09 - CHAN (CENTRELUN) THIRD-TYPE BUY / SELL POINTS")
    print("=" * W)
    print("event study, not a strategy. cost = " + format(COST_PIPS, ".1f")
          + " pip round trip (5 USD/lot/side, EURUSD 1 pip = 10 USD/lot)")
    print("look-ahead control: every structure carries a confirm index; entry is")
    print("                    the open of the bar AFTER confirmation.")
    print("definition: containment merge -> fenxing -> new-bi (gap>=" + str(MIN_GAP)
          + ") -> 3-stroke zhongshu -> third-type point.")
    print("no beichi, no duan: those cannot be decided without hindsight.")

    report = {}
    for scale in args.scales.split(","):
        scale = scale.strip().upper()
        if scale == "D1":
            m1 = load_m1_bj(Path(args.m1))
            bars, _ = aggregate_to(m1, "D1", FX_DAY_START)
        elif scale == "M5":
            bars, _quality = load_m5(Path(args.m1))
        else:
            continue
        edf, structure = chan_signals(bars)
        print("=" * W)
        print("[" + scale + "] bars " + format(len(bars), ",")
              + "  merged " + format(structure["merged_bars"], ",")
              + "  fenxing " + format(structure["fenxing"], ",")
              + "  bi " + format(structure["bi"], ",")
              + "  zhongshu " + format(structure["zhongshu"], ",")
              + "  signals " + format(structure["signals"], ","))
        if len(edf) == 0:
            print("  no signal produced; scale skipped")
            report[scale] = {"structure": structure, "cells": {}}
            continue
        edf = build_events(edf, bars)
        ts = pd.to_datetime(bars.index)
        years = (ts.max() - ts.min()).days / 365.25
        print("  span " + str(ts.min().date()) + " .. " + str(ts.max().date())
              + "  (" + format(years, ".2f") + " y)")
        for kind in ("buy", "sell"):
            print("    " + kind + ": " + format(int((edf["kind"] == kind).sum()), ","))
        cells = {}
        print("  " + format("H", "<4") + format("kind", "<6") + format("n", ">8")
              + format("gross_p", ">10") + format("net_p", ">9")
              + format("t", ">7") + format("blk CI95", ">20")
              + format("IS", ">9") + format("OOS", ">9"))
        for H in HORIZONS:
            res = analyze(edf, scale, H, years)
            for kind, st in res.items():
                ci = st.get("block_ci95") or {}
                iv = ci.get("mean_ci95")
                cis = ("[" + format(iv[0], ".2f") + "," + format(iv[1], ".2f") + "]"
                       if iv else "-")
                sd = st.get("std_pips")
                mean = st.get("mean_pips")
                t = mean / (sd / np.sqrt(st["n"])) if sd else None
                print("  " + format(H, "<4") + format(kind, "<6")
                      + format(st["n"], ">8,")
                      + format(mean, ">+10.3f")
                      + format(st.get("mean_net_pips"), ">+9.3f")
                      + format(t, ">7.2f") + format(cis, ">20")
                      + format(st.get("is_mean"), ">9.2f")
                      + format(st.get("oos_mean"), ">9.2f"))
                cells["H" + str(H) + "_" + kind] = st
        report[scale] = {"structure": structure, "years": round(years, 2),
                         "cells": cells}
        edf.to_csv(out_dir / ("exp09_" + scale + "_events.csv"), index=False)

    print("=" * W)
    print("[VERDICT] gate: |t| >= 2 and n >= " + str(MIN_N_FOR_VERDICT)
          + " and net > 0 after " + format(COST_PIPS, ".1f") + " pip")
    for scale, blk in report.items():
        for key, st in (blk.get("cells") or {}).items():
            sd = st.get("std_pips")
            t = st["mean_pips"] / (sd / np.sqrt(st["n"])) if sd else 0.0
            net = st.get("mean_net_pips") or 0.0
            ok = abs(t) >= 2 and st["n"] >= MIN_N_FOR_VERDICT and net > 0
            why = []
            if st["n"] < MIN_N_FOR_VERDICT:
                why.append("n too small to judge")
            if abs(t) < 2:
                why.append("not significant")
            if net <= 0:
                why.append("negative after cost")
            print("  " + format(scale + " " + key, "<18")
                  + format("PASS" if ok else "fail", "<6")
                  + "n=" + format(st["n"], ",") + "  t=" + format(t, "+.2f")
                  + "  net=" + format(net, "+.2f") + "p  "
                  + ("; ".join(why) if why else ""))

    print("=" * W)
    print("[SCOPE]")
    print("  * One fixed Chan formalisation; no variant scanned. A negative")
    print("    result may be a property of this definition, not of Chan.")
    print("  * No beichi and no duan, because they are hindsight-only.")
    print("  * Entry at open[confirm+1]; signal uses only bars <= confirm.")
    print("  * Cost " + format(COST_PIPS, ".1f") + " pip round trip, no swap "
          "(stated: swap = 0).")
    print("  * Pre-slippage; fixed +1 unit; no stops or sizing.")

    rp = out_dir / "exp09_report.json"
    rp.write_text(json.dumps({
        "experiment": "exp09_chan_third_point",
        "type": "event study of Chan third-type buy/sell points",
        "question": "after a confirmed third-type point, does price continue in "
                    "the implied direction by more than the execution cost?",
        "cost_pips": COST_PIPS,
        "cost_derivation": "5 USD per lot per side; EURUSD 1 pip = 10 USD/lot; "
                           "round trip = 1.0 pip",
        "definition": {
            "merge": "direction-aware containment merge",
            "fenxing": "3-bar top/bottom, confirmed at the third bar",
            "bi": "new-bi, opposite fenxing >= MIN_GAP merged bars apart",
            "zhongshu": "overlap of 3 consecutive strokes, ZG/ZD",
            "third_point": "break out -> pull back without re-entering -> "
                           "break out again",
            "excluded": ["beichi", "duan"],
            "excluded_reason": "cannot be decided without hindsight",
        },
        "look_ahead_control": "every structure carries a confirm index; entry "
                              "at open[confirm+1]",
        "params": {"MIN_GAP": MIN_GAP, "MAX_WAIT": MAX_WAIT,
                   "HORIZONS": list(HORIZONS), "OOS_YEAR": OOS_YEAR,
                   "FX_DAY_START": FX_DAY_START, "SEED": SEED,
                   "N_BOOT": N_BOOT},
        "scales": report,
        "caveats": [
            "Single fixed formalisation; other Chan variants may differ.",
            "Excludes beichi and duan by design.",
            "Pre-slippage, fixed +1 unit, no stops or sizing.",
        ],
    }, ensure_ascii=False, indent=2, default=str))
    print("report -> " + str(rp))
    print("=" * W)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
