#!/usr/bin/env python3
"""Exp05 -- EURUSD Breakout Continuation at LONGER bar scales.

Why this exists
---------------
Exp04 (frozen: artifacts/research/eurusd_breakout/) answered the
continuation question on M5 and refuted it. All eight cells
(up/down x 1h/4h x IS/OOS) were negative, with a raw directional effect of
about -0.37 pips against a 1.5 pip round-trip cost.

The structural problem Exp04 exposed is not the SIGN, it is the MAGNITUDE:
a 0.3-0.5 pip raw effect cannot pay a 1.5 pip round trip, so no amount of
entry/stop/exit engineering rescues it at that scale. The agreed next step
is therefore to change the BAR SCALE while keeping the signal definition
and the measurement method identical, and ask whether a longer holding
period produces an effect large enough to clear cost.

Identical by construction (nothing was tuned)
---------------------------------------------
    up   breakout : close[i] > max(high[i-12 .. i-1])
    down breakout : close[i] < min(low[i-12 .. i-1])
    entry         : open  of bar i+1   (never the signal close)
    exit          : close of bar i+H   for H in {12, 48}
    return        : signed so positive always means "continued"

LOOKBACK stays 12 bars and HORIZONS stay {12, 48} bars at every scale.
Because the bar scale changes, those bar counts map onto different calendar
spans:

    scale  bar        lookback 12     horizon 12      horizon 48
    M5     5min       60min           60min           240min
    H4     4h         48h             48h             192h
    D1     1 FX day   12 days         12 days         48 days

The bar counts are deliberately NOT rescaled to hold a constant calendar
window. Keeping the COUNT fixed is the choice that adds no new degree of
freedom; rescaling would inject one. Consequences to remember when reading:

  * raw pip magnitudes grow with the bar scale simply because more time
    elapses. Pips are therefore NOT comparable across scales.
  * the comparable statistic is reported alongside every cell:
        effect size = mean / std  (drift per unit of volatility)
  * longer holds incur overnight financing, charged by the number of FX day
    boundaries crossed, so it is measured explicitly ("nights") and swept
    over {0, 0.5, 1.0} pip per night rather than assumed away.

Reuses, modifies nothing
------------------------
load_m5 / PIP / STORED_TO_BEIJING from eurusd_reversal_v1_m5.py, the
IS/OOS split already used by exp01-exp04 (year < 2016 = IS), and the
statistics layer of Exp04 (stats, block_bootstrap, nonoverlap_mask,
concentration) so every reported number uses the same estimator as the
frozen Exp04 report. Nothing in Reversal V1, exp01-exp04, the raw parquet
or any existing artifact is modified.

M5 is recomputed here ONLY as an anchor: those numbers must reproduce the
frozen Exp04 report. If they do not, this run is invalid. M5 per-event rows
are not written to disk again (Exp04 already published them).

Bar validity: this differs from Exp04 and is made explicit
----------------------------------------------------------
Exp04 treated two consecutive M5 bars more than 5 minutes apart as a break
and dropped any window spanning one. At longer scales that rule no longer
works: the index of H4/D1 bars is naturally irregular across weekends,
while a MISSING weekday is invisible because the index simply skips it.
Validity is therefore judged by DATA DENSITY: every bar carries the number
of M1 observations inside it, and a bar holding less than MIN_M1_RATIO of
the theoretical M1 count is flagged sparse. A window containing a sparse
bar is dropped, exactly as a window spanning a gap was dropped in Exp04.
The realised M1 count distribution is reported so the threshold itself can
be judged rather than trusted.
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
from exp04_breakout_continuation import (                            # noqa: E402
    build_events as build_events_m5,
    stats,
    block_bootstrap,
    nonoverlap_mask,
    concentration,
    COST_PIPS,
    LOOKBACK,
    HORIZONS,
    OOS_YEAR,
    N_BOOT,
    SEED,
)

REPO = Path(__file__).resolve().parents[2]
DEFAULT_M1 = REPO / "artifacts/histdata_v9/parsed/eurusd_2000-2026_bars.parquet"
DEFAULT_OUT = REPO / "artifacts/research/eurusd_breakout_longer"

FX_DAY_START = 6        # same FX day convention as eurusd_reversal_v1_m5
SCALES = ("H4", "D1")   # M5 handled separately, as the reproducibility anchor
EXPECTED_M1 = {"H4": 240, "D1": 1440}     # M1 ticks inside a full bar
MIN_M1_RATIO = 0.5                        # below this share -> sparse bar
SWAP_PER_NIGHT = (0.0, 0.5, 1.0)          # reported sweep, not a chosen value
MIN_N_FOR_VERDICT = 200                   # below this a cell cannot be judged
W = 132

SCALE_TIME_LABEL = {
    "M5": {12: "1h", 48: "4h"},
    "H4": {12: "2d", 48: "8d"},
    "D1": {12: "12td", 48: "48td"},
}


def hlab(scale: str, H: int) -> str:
    return SCALE_TIME_LABEL.get(scale, {}).get(H, str(H))


# ----------------------------------------------------------------------
def load_m1_bj(path: Path) -> pd.DataFrame:
    """Raw M1 -> Beijing time. Same conversion constant as load_m5."""
    df = pd.read_parquet(path, columns=["ts", "open", "high", "low", "close"])
    df.index = pd.to_datetime(df["ts"]) + STORED_TO_BEIJING
    df = df.drop(columns=["ts"])
    df.index.name = "bj"
    return df


def bar_labels(idx: pd.DatetimeIndex, kind: str, fx_day_start: int) -> pd.DatetimeIndex:
    """Bucket start timestamps, aligned to the FX day origin.

    Both scales derive from the same shifted origin, so every FX day
    contains exactly six H4 buckets starting at 06:00 Beijing.
    """
    shifted = idx - pd.Timedelta(hours=fx_day_start)
    if kind == "D1":
        lab = shifted.floor("D")
    elif kind == "H4":
        lab = shifted.floor("4h")
    else:
        raise ValueError("unknown bar kind " + str(kind))
    return lab + pd.Timedelta(hours=fx_day_start)


def aggregate_to(m1: pd.DataFrame, kind: str, fx_day_start: int):
    """M1 -> OHLC bars plus the M1 count inside each bar."""
    lab = pd.Series(bar_labels(m1.index, kind, fx_day_start), index=m1.index)
    g = m1.groupby(lab)
    bars = g.agg(open=("open", "first"), high=("high", "max"),
                 low=("low", "min"), close=("close", "last"))
    counts = g.size()
    bars = bars.dropna(subset=["open", "high", "low", "close"])
    counts = counts.reindex(bars.index)
    bars.index.name = "bj"
    return bars, counts


# ----------------------------------------------------------------------
def build_events_long(bars: pd.DataFrame, counts: pd.Series, kind: str,
                      lookback: int, horizons: tuple, fx_day_start: int,
                      min_ratio: float = MIN_M1_RATIO):
    """Same signal and entry/exit rules as Exp04, but window validity is
    judged by M1 density instead of index spacing. No future data is read
    when deciding whether a signal exists or where the entry is.
    """
    n = len(bars)
    ts = bars.index
    o = bars["open"].to_numpy(float)
    h = bars["high"].to_numpy(float)
    lo = bars["low"].to_numpy(float)
    c = bars["close"].to_numpy(float)
    cnt = counts.reindex(bars.index).to_numpy(float)

    expected = EXPECTED_M1[kind]
    thresh = min_ratio * expected
    sparse = cnt < thresh
    scum = np.concatenate([[0], np.cumsum(sparse.astype(np.int64))])

    # trading-day ordinal, used only for overnight-financing accounting
    dlabel = bar_labels(ts, "D1", fx_day_start)
    dnum = np.asarray((dlabel - dlabel[0]).days, dtype=np.int64)

    prior_hi = pd.Series(h).rolling(lookback).max().shift(1).to_numpy()
    prior_lo = pd.Series(lo).rolling(lookback).min().shift(1).to_numpy()
    up_idx = np.flatnonzero(c > prior_hi)
    dn_idx = np.flatnonzero(c < prior_lo)

    ledger = {
        "kind": kind,
        "bars": int(n),
        "lookback_bars": int(lookback),
        "expected_m1_per_bar": int(expected),
        "min_m1_ratio": min_ratio,
        "sparse_threshold_m1": int(thresh),
        "m1_count_median": round(float(np.median(cnt)), 1),
        "m1_count_p10": round(float(np.percentile(cnt, 10)), 1),
        "m1_count_p90": round(float(np.percentile(cnt, 90)), 1),
        "sparse_bars": int(sparse.sum()),
        "sparse_bar_pct": round(float(sparse.mean()), 4),
        "total_signals_considered": int(len(up_idx) + len(dn_idx)),
        "up_raw": int(len(up_idx)), "down_raw": int(len(dn_idx)),
    }

    parts = []
    for direction, idx in (("up", up_idx), ("down", dn_idx)):
        if len(idx) == 0:
            continue
        lb_clean = (scum[idx] - scum[idx - lookback]) == 0
        i_entry = np.minimum(idx + 1, n - 1)
        entry = o[i_entry]

        d = pd.DataFrame({
            "bar_i": idx,
            "signal_bar": ts[idx].strftime("%Y-%m-%d %H:%M:%S"),
            "date": ts[idx].strftime("%Y-%m-%d"),
            "year": ts[idx].year,
            "direction": direction,
            "signal_close": c[idx],
            "prior_high": prior_hi[idx],
            "prior_low": prior_lo[idx],
            "entry_bar": ts[i_entry].strftime("%Y-%m-%d %H:%M:%S"),
            "entry_px": entry,
            "m1_count": cnt[idx],
            "valid_lookback": lb_clean,
        })
        for H in horizons:
            pos_ok = (idx + H) < n
            hold_clean = (scum[np.minimum(idx + H, n)] - scum[idx]) == 0
            iH = np.minimum(idx + H, n - 1)
            exit_px = c[iH]
            r = ((exit_px - entry) / PIP if direction == "up"
                 else (entry - exit_px) / PIP)
            nights = dnum[iH] - dnum[i_entry]
            ok = lb_clean & pos_ok & hold_clean
            d["ret_" + str(H)] = np.where(ok, r, np.nan)
            d["exit_" + str(H) + "_px"] = np.where(ok, exit_px, np.nan)
            d["nights_" + str(H)] = np.where(ok, nights, np.nan)
            d["valid_" + str(H)] = ok
            ledger.setdefault("H" + str(H), {})[direction] = {
                "raw": int(len(idx)),
                "dropped_lookback_sparse": int((~lb_clean).sum()),
                "dropped_position": int((lb_clean & ~pos_ok).sum()),
                "dropped_holding_sparse": int((lb_clean & pos_ok & ~hold_clean).sum()),
                "kept": int(ok.sum()),
            }
        parts.append(d)

    edf = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    if len(edf):
        edf = edf.sort_values("signal_bar").reset_index(drop=True)
    return edf, ledger


# ----------------------------------------------------------------------
def analyze_scale(edf: pd.DataFrame, cost: float, oos_year: int,
                  horizons: tuple) -> dict:
    """Every statistic for one bar scale, per direction and horizon."""
    out = {}
    for H in horizons:
        for dd in ("up", "down"):
            sub = edf[(edf["direction"] == dd) & edf["valid_" + str(H)]]
            r = sub["ret_" + str(H)].to_numpy(float)
            s = stats(r, cost=cost)
            if s.get("n", 0) == 0:
                out[dd + "_" + str(H)] = s
                continue
            dates = sub["date"].to_numpy()
            ncol = "nights_" + str(H)
            if ncol in sub.columns:
                nights = sub[ncol].to_numpy(float)
                s["mean_nights"] = round(float(np.nanmean(nights)), 2)
                s["swap_sensitivity"] = {
                    format(sw, "g"): round(float(np.nanmean(r - cost - sw * nights)), 4)
                    for sw in SWAP_PER_NIGHT
                }
            else:
                # the M5 anchor reuses Exp04 events, which carry no financing column
                nights = None
                s["mean_nights"] = None
                s["swap_sensitivity"] = None
            s["bootstrap"] = block_bootstrap(r, dates, N_BOOT, SEED)
            s["effect_per_sd"] = (round(s["mean_pips"] / s["std_pips"], 5)
                                  if s.get("std_pips") else None)
            order = np.argsort(sub["bar_i"].to_numpy(), kind="stable")
            bar_sorted = sub["bar_i"].to_numpy()[order]
            r_sorted = r[order]
            mask = nonoverlap_mask(bar_sorted, H)
            r_no = r_sorted[mask]
            s["nonoverlap"] = {
                "n": int(mask.sum()),
                "share": round(float(mask.mean()), 4),
                "mean_pips": (round(float(np.nanmean(r_no)), 4)
                              if len(r_no) else None),
                "mean_net_pips": (round(float(np.nanmean(r_no - cost)), 4)
                                  if len(r_no) else None),
            }
            s["overlap_rate"] = round(1 - float(mask.mean()), 4)
            s["phase"] = {}
            for ph, sel in (("IS", sub["year"] < oos_year),
                            ("OOS", sub["year"] >= oos_year)):
                rp = sub.loc[sel, "ret_" + str(H)].to_numpy(float)
                sp = stats(rp, cost=cost)
                if sp.get("n", 0):
                    sp["bootstrap"] = block_bootstrap(
                        rp, sub.loc[sel, "date"].to_numpy(), N_BOOT, SEED)
                s["phase"][ph] = sp
            grp = sub.groupby("year")["ret_" + str(H)]
            yearly = pd.DataFrame({"n": grp.size(), "mean": grp.mean()})
            s["yearly"] = {int(y): {"n": int(row["n"]),
                                    "mean_pips": round(float(row["mean"]), 4)}
                           for y, row in yearly.iterrows()}
            s["concentration"] = concentration(yearly, "mean", "n")
            out[dd + "_" + str(H)] = s
    return out


def classify(cells: dict, horizons: tuple) -> dict:
    """Apply the pre-committed three-tier framework to one bar scale.

    The rules were fixed before any result was seen; nothing is adjusted
    afterwards. Every component is returned so the verdict can be audited
    rather than trusted.
    """
    cm = {(dd, H): cells.get(dd + "_" + str(H), {})
          for dd in ("up", "down") for H in horizons}
    ns = [c.get("n", 0) for c in cm.values()]
    min_n = min(ns) if ns else 0
    if min_n < MIN_N_FOR_VERDICT:
        return {"verdict": "证据不足 / INSUFFICIENT EVIDENCE",
                "reason": ["smallest cell n=" + format(min_n, ",") + " < "
                           + str(MIN_N_FOR_VERDICT)],
                "min_cell_n": int(min_n),
                "gross_positive": None, "net_positive": None,
                "sign_consistent": None, "phase_consistent": None,
                "best_year_abs_share": None}

    means = [c["mean_pips"] for c in cm.values()]
    consistent = len(set(np.sign(means).tolist())) == 1
    nets = [c["mean_net_pips"] for c in cm.values()]
    gross_pos = max(means) > 0
    net_pos = max(nets) > 0

    ph_consistent = True
    for c in cm.values():
        base = np.sign(c["mean_pips"])
        for name in ("IS", "OOS"):
            p = c.get("phase", {}).get(name, {})
            if p.get("n", 0) and np.sign(p["mean_pips"]) != base:
                ph_consistent = False

    shares = [c.get("concentration") or {} for c in cm.values()]
    top1 = max((x.get("best_year_abs_share") or 0.0 for x in shares), default=0.0)
    conc_ok = top1 <= 0.5

    if not net_pos:
        verdict = "暂不成立 / NOT ESTABLISHED"
        reason = ["every cell negative after round-trip cost"]
    elif not consistent:
        verdict = "暂不成立 / NOT ESTABLISHED"
        reason = ["direction inconsistent across direction x horizon"]
    elif not ph_consistent:
        verdict = "暂不成立 / NOT ESTABLISHED"
        reason = ["IS/OOS sign mismatch"]
    elif not conc_ok:
        verdict = "暂不成立 / NOT ESTABLISHED"
        reason = ["best single year carries " + format(top1, ".0%")
                  + " of |yearly contribution|"]
    else:
        verdict = "值得继续 / WORTH CONTINUING"
        reason = ["gross positive, survives round-trip cost, IS/OOS consistent, "
                  "not year-concentrated"]
    return {"verdict": verdict, "reason": reason, "min_cell_n": int(min_n),
            "gross_positive": bool(gross_pos), "net_positive": bool(net_pos),
            "sign_consistent": bool(consistent),
            "phase_consistent": bool(ph_consistent),
            "best_year_abs_share": round(float(top1), 4)}


def pooled_concentration(edf: pd.DataFrame, H: int) -> dict | None:
    """Yearly contribution with up and down POOLED into the same year.

    Pooling is done on the raw per-year distributions, not by reusing the
    per-direction numbers, so best/worst year statistics really describe
    the combined sample.
    """
    if edf is None or len(edf) == 0 or ("valid_" + str(H)) not in edf.columns:
        return None
    sub = edf[edf["valid_" + str(H)]]
    if len(sub) == 0:
        return None
    grp = sub.groupby("year")["ret_" + str(H)]
    yearly = pd.DataFrame({"n": grp.size(), "mean": grp.mean()})
    return concentration(yearly, "mean", "n")


# ----------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(
        description="Exp05 EURUSD breakout continuation on longer bar scales")
    ap.add_argument("--m1", default=str(DEFAULT_M1))
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT))
    ap.add_argument("--lookback", type=int, default=LOOKBACK)
    ap.add_argument("--horizons", default=",".join(str(h) for h in HORIZONS))
    ap.add_argument("--cost-pips", type=float, default=COST_PIPS)
    ap.add_argument("--oos-year", type=int, default=OOS_YEAR)
    ap.add_argument("--fx-day-start", type=int, default=FX_DAY_START)
    ap.add_argument("--min-m1-ratio", type=float, default=MIN_M1_RATIO)
    args = ap.parse_args()

    horizons = tuple(int(x) for x in args.horizons.split(",") if x.strip())
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * W)
    print("Exp05 - EURUSD Breakout Continuation - LONGER BAR SCALES - EVENT STUDY")
    print("=" * W)

    m5, quality = load_m5(Path(args.m1))
    m1 = load_m1_bj(Path(args.m1))
    print("data       : M1 rows " + format(len(m1), ",") + " -> M5 bars "
          + format(quality["m5_bars"], ","))
    print("range      : " + quality["m5_range"][0] + " .. " + quality["m5_range"][1]
          + " (Beijing)")
    print("timezone   : stored EST(UTC-5), Beijing = stored + 13h; FX day starts "
          + format(args.fx_day_start, "02d") + ":00 Beijing")
    print("signal     : close[i] beyond the prior " + str(args.lookback)
          + " completed bars (signal bar excluded); entry = open of bar i+1")
    print("cost       : " + str(args.cost_pips)
          + " pips round trip ASSUMED (same as exp01-04)")
    print("financing  : nights = FX day boundaries crossed, swept over "
          + ", ".join(str(s) for s in SWAP_PER_NIGHT)
          + " pip/night (reported, NOT chosen)")
    print("IS/OOS     : IS year < " + str(args.oos_year) + ", OOS year >= "
          + str(args.oos_year) + " (same split as exp01-04)")
    print("validity   : a bar is sparse if its M1 count < " + format(args.min_m1_ratio, "g")
          + " x full bar (H4=" + str(EXPECTED_M1["H4"]) + ", D1="
          + str(EXPECTED_M1["D1"]) + " M1); any window containing a sparse bar is dropped")
    print("NOTE       : lookback/horizon COUNT is fixed at 12/{"
          + ",".join(str(h) for h in horizons)
          + "} bars on every scale, so the calendar span grows with the bar scale.")
    print("             Compare effect_per_sd (mean/std) across scales, NOT raw pips.")

    results = {}
    anchor = {}
    events_frames = []

    # ---------------- M5 anchor: must reproduce Exp04 ----------------
    edf_m5, led_m5 = build_events_m5(m5, args.lookback, horizons)
    anchor = analyze_scale(edf_m5, args.cost_pips, args.oos_year, horizons)
    anchor_meta = {"bars": led_m5["bars"],
                   "gap_bars_total": led_m5["gap_bars_total"],
                   "ledger": led_m5}
    pool = {"M5": {str(H): pooled_concentration(edf_m5, H) for H in horizons}}
    print("-" * W)
    print("[A] M5 REPRODUCIBILITY ANCHOR (must match the frozen Exp04 report)")
    for H in horizons:
        for dd in ("up", "down"):
            s = anchor.get(dd + "_" + str(H), {})
            lab = hlab("M5", H)
            print("  M5 " + format(dd, "<5") + format(lab, "<8")
                  + "n " + format(s.get("n", 0), ">8,")
                  + "  mean " + format(s.get("mean_pips", float("nan")), "+.4f") + "p"
                  + "  net " + format(s.get("mean_net_pips", float("nan")), "+.4f") + "p"
                  + "  std " + format(s.get("std_pips", float("nan")), ".3f"))

    # ---------------- longer scales ----------------
    for kind in SCALES:
        bars, counts = aggregate_to(m1, kind, args.fx_day_start)
        edf, ledger = build_events_long(
            bars, counts, kind, args.lookback, horizons,
            args.fx_day_start, args.min_m1_ratio)
        res = analyze_scale(edf, args.cost_pips, args.oos_year, horizons)
        rng = [str(bars.index.min()), str(bars.index.max())]
        res["_meta"] = {"bars": ledger["bars"], "ledger": ledger, "range": rng}
        pool[kind] = {str(H): pooled_concentration(edf, H) for H in horizons}
        results[kind] = res
        if len(edf):
            e = edf.copy()
            e.insert(0, "scale", kind)
            events_frames.append(e)

        print("-" * W)
        print("[B] " + kind + " bars: " + format(ledger["bars"], ",") + " bars | "
              + rng[0] + " .. " + rng[1] + " | sparse bars "
              + format(ledger["sparse_bars"], ",") + " ("
              + format(ledger["sparse_bar_pct"], ".2%") + ")")
        print("    M1 per bar: median " + format(ledger["m1_count_median"], ".0f")
              + ", p10 " + format(ledger["m1_count_p10"], ".0f")
              + ", p90 " + format(ledger["m1_count_p90"], ".0f")
              + " of " + str(ledger["expected_m1_per_bar"])
              + " (sparse threshold " + str(ledger["sparse_threshold_m1"]) + ")")
        for H in horizons:
            for dd in ("up", "down"):
                e_ = ledger.get("H" + str(H), {}).get(dd, {})
                lab = hlab(kind, H)
                print("      H=" + format(lab, "<6") + format(dd, "<6")
                      + "raw " + format(e_.get("raw", 0), ">7,")
                      + " | drop lb-sparse "
                      + format(e_.get("dropped_lookback_sparse", 0), ">5,")
                      + " | drop no-position "
                      + format(e_.get("dropped_position", 0), ">4,")
                      + " | drop hold-sparse "
                      + format(e_.get("dropped_holding_sparse", 0), ">5,")
                      + " | kept " + format(e_.get("kept", 0), ">7,"))

    # ---------------- main directional table ----------------
    print("=" * W)
    print("[C] CROSS-SCALE DIRECTIONAL RESULT (+ = continued in the breakout direction)")
    print("  " + format("scale", "<6") + format("dir", "<6") + format("horiz", "<8")
          + format("n", ">8") + format("mean_p", ">10") + format("std_p", ">10")
          + format("mean/sd", ">10") + format("med_p", ">9") + format("pos%", ">7")
          + format("net_p", ">10"))
    for kind in ("M5",) + SCALES:
        res = anchor if kind == "M5" else results[kind]
        for H in horizons:
            for dd in ("up", "down"):
                s = res.get(dd + "_" + str(H), {})
                if not s.get("n", 0):
                    continue
                lab = hlab(kind, H)
                print("  " + format(kind, "<6") + format(dd, "<6")
                      + format(lab, "<8") + format(s["n"], ">8,")
                      + format(s["mean_pips"], "+10.4f")
                      + format(s["std_pips"], "10.3f")
                      + format(s["effect_per_sd"], "+10.5f")
                      + format(s["median_pips"], "+9.3f")
                      + format(s["pos_share"] * 100, "6.1f") + "%"
                      + format(s["mean_net_pips"], "+10.4f"))
    print("  mean/sd = mean_pips / std_pips: the scale-free effect size. Compare THIS "
          "across scales, not pips.")

    # ---------------- financing sensitivity ----------------
    print("=" * W)
    print("[D] OVERNIGHT FINANCING (round trip still " + str(args.cost_pips) + "p; "
          "values are mean NET pips)")
    print("  " + format("scale", "<6") + format("dir", "<6") + format("horiz", "<8")
          + format("nights", ">8") + format("swap0", ">10") + format("swap0.5", ">10")
          + format("swap1.0", ">10"))
    for kind in SCALES:
        res = results[kind]
        for H in horizons:
            for dd in ("up", "down"):
                s = res.get(dd + "_" + str(H), {})
                if not s.get("n", 0):
                    continue
                sw = s["swap_sensitivity"]
                lab = hlab(kind, H)
                print("  " + format(kind, "<6") + format(dd, "<6")
                      + format(lab, "<8") + format(s["mean_nights"], "8.1f")
                      + format(float(sw["0"]), "+10.4f")
                      + format(float(sw["0.5"]), "+10.4f")
                      + format(float(sw["1"]), "+10.4f"))

    # ---------------- IS / OOS ----------------
    print("=" * W)
    print("[E] IS (<" + str(args.oos_year) + ") vs OOS (>=" + str(args.oos_year) + ")")
    print("  " + format("scale", "<6") + format("dir", "<6") + format("horiz", "<8")
          + format("phase", "<6") + format("n", ">8") + format("mean_p", ">10")
          + format("net_p", ">10") + format("effect/sd", ">11"))
    for kind in ("M5",) + SCALES:
        res = anchor if kind == "M5" else results[kind]
        for H in horizons:
            for dd in ("up", "down"):
                s = res.get(dd + "_" + str(H), {})
                if not s.get("n", 0):
                    continue
                lab = hlab(kind, H)
                for ph in ("IS", "OOS"):
                    p = s.get("phase", {}).get(ph, {})
                    if not p.get("n", 0):
                        continue
                    eff = (p["mean_pips"] / p["std_pips"]) if p.get("std_pips") else float("nan")
                    print("  " + format(kind, "<6") + format(dd, "<6")
                          + format(lab, "<8") + format(ph, "<6")
                          + format(p["n"], ">8,")
                          + format(p["mean_pips"], "+10.4f")
                          + format(p["mean_net_pips"], "+10.4f")
                          + format(eff, "+11.5f"))

    # ---------------- uncertainty ----------------
    print("=" * W)
    print("[F] UNCERTAINTY (naive SE understates it because windows overlap; "
          "use the block-bootstrap CI)")
    print("  " + format("scale", "<6") + format("dir", "<6") + format("horiz", "<8")
          + format("n", ">8") + format("mean_p", ">10") + format("naiveSE", ">10")
          + format("boot_CI95", ">26") + format("sig?", ">7"))
    for kind in ("M5",) + SCALES:
        res = anchor if kind == "M5" else results[kind]
        for H in horizons:
            for dd in ("up", "down"):
                s = res.get(dd + "_" + str(H), {})
                if not s.get("n", 0):
                    continue
                b = s.get("bootstrap") or {}
                ci = b.get("mean_ci95", [float("nan"), float("nan")])
                lab = hlab(kind, H)
                lo, hi = float(ci[0]), float(ci[1])
                sig = "yes" if (lo > 0 or hi < 0) else "NO"
                ci_s = "[" + format(lo, "+.4f") + ", " + format(hi, "+.4f") + "]"
                print("  " + format(kind, "<6") + format(dd, "<6")
                      + format(lab, "<8") + format(s["n"], ">8,")
                      + format(s["mean_pips"], "+10.4f")
                      + format(s["naive_se"], "10.4f")
                      + format(ci_s, ">26") + format(sig, ">7"))

    # ---------------- overlap ----------------
    print("=" * W)
    print("[G] SIGNAL / WINDOW OVERLAP (row order != bar order; measured on bar positions)")
    print("  " + format("scale", "<6") + format("dir", "<6") + format("horiz", "<8")
          + format("signals", ">9") + format("nonoverlap", ">11")
          + format("overlap%", ">10") + format("nonovl_mean_p", ">15")
          + format("nonovl_net_p", ">15"))
    for kind in SCALES:
        res = results[kind]
        for H in horizons:
            for dd in ("up", "down"):
                s = res.get(dd + "_" + str(H), {})
                if not s.get("n", 0):
                    continue
                nz = s.get("nonoverlap", {})
                lab = hlab(kind, H)
                print("  " + format(kind, "<6") + format(dd, "<6")
                      + format(lab, "<8") + format(s["n"], ">9,")
                      + format(nz.get("n", 0), ">11,")
                      + format(s["overlap_rate"] * 100, "9.1f") + "%"
                      + format(nz.get("mean_pips", float("nan")), "+15.4f")
                      + format(nz.get("mean_net_pips", float("nan")), "+15.4f"))

    # ---------------- yearly ----------------
    print("=" * W)
    print("[H] YEARLY CONCENTRATION (up + down pooled, GROSS pips)")
    print("  " + format("scale", "<6") + format("horiz", "<8")
          + format("years+", ">8") + format("years-", ">8") + format("best_y", ">8")
          + format("best_p", ">11") + format("worst_y", ">9") + format("worst_p", ">11")
          + format("best|share|", ">12") + format("ex_worst_p", ">12"))
    for kind in ("M5",) + SCALES:
        res = anchor if kind == "M5" else results[kind]
        for H in horizons:
            cc = pool.get(kind, {}).get(str(H))
            if not cc:
                continue
            lab = hlab(kind, H)
            print("  " + format(kind, "<6") + format(lab, "<8")
                  + format(cc["years_positive"], ">8")
                  + format(cc["years_negative"], ">8")
                  + format(cc["best_year"], ">8")
                  + format(cc["best_year_pips"], "+11.1f")
                  + format(cc["worst_year"], ">9")
                  + format(cc["worst_year_pips"], "+11.1f")
                  + format(cc["best_year_abs_share"] * 100, "11.1f") + "%"
                  + format(cc["ex_worst_year_pips"], "+12.1f"))

    # ---------------- verdicts ----------------
    print("=" * W)
    print("[I] VERDICT per scale, using the pre-committed three-tier framework")
    verdicts = {}
    for kind in ("M5",) + SCALES:
        res = anchor if kind == "M5" else results[kind]
        v = classify(res, horizons)
        verdicts[kind] = v
        print("  " + kind + ": " + v["verdict"])
        detail = ("      min cell n = " + format(v["min_cell_n"], ",")
                  + " | gross>0 " + str(v["gross_positive"])
                  + " | net>0 " + str(v["net_positive"])
                  + " | sign consistent " + str(v["sign_consistent"])
                  + " | IS/OOS consistent " + str(v["phase_consistent"]))
        share = v["best_year_abs_share"]
        detail = detail + (" | best-year |share| " + format(share, ".1%")
                           if share is not None else " | best-year |share| n/a")
        print(detail)
        for r_ in v["reason"]:
            print("      reason: " + r_)

    print("=" * W)
    print("[J] SCOPE OF THIS RESULT")
    print("  * Event study: no stops, targets, sizing, session filter or signal filter.")
    print("  * Signals recur inside the same move and windows overlap ([G]); the")
    print("    bootstrap CI in [F] absorbs that dependence, the naive SE does not.")
    print("  * Raw pips are NOT comparable across bar scales because the calendar")
    print("    span differs. mean/sd is the comparable statistic.")
    print("  * Round-trip cost is assumed, not measured; overnight financing is swept")
    print("    rather than assumed. Real fills add slippage on top.")
    print("  * Even a direction that survives cost is not yet a tradable strategy:")
    print("    entry, stop, exit, capacity and execution still have to be researched.")

    # ---------------- artifacts ----------------
    csv_path = out_dir / "exp05_events.csv"
    if events_frames:
        all_ev = pd.concat(events_frames, ignore_index=True)
        all_ev.to_csv(csv_path, index=False)
    else:
        all_ev = pd.DataFrame()
        csv_path.write_text("")

    report = {
        "experiment": "exp05_eurusd_breakout_continuation_longer_horizon",
        "type": "event study, not a strategy",
        "question": "after a breakout of the prior 12 completed bars, does EURUSD "
                    "continue? Measured on longer bar scales because Exp04 showed "
                    "the M5 effect is far too small to pay cost.",
        "data": {
            "source": str(args.m1),
            "m1_rows": int(len(m1)),
            "timezone": "stored EST(UTC-5); Beijing = stored + 13h",
            "fx_day_start_beijing_hour": args.fx_day_start,
            "range_beijing": [str(m1.index.min()), str(m1.index.max())],
            "missing_data_policy": "a bar holding less than min_m1_ratio of the "
                                   "theoretical M1 count is sparse; any lookback or "
                                   "holding window containing a sparse bar is dropped "
                                   "and the drop is counted",
        },
        "method": {
            "signal_up": "close[i] > max(high[i-lookback .. i-1])",
            "signal_down": "close[i] < min(low[i-lookback .. i-1])",
            "entry": "open of bar i+1",
            "exit": "close of bar i+H",
            "return": "signed so positive always means continued",
            "lookback_bars": args.lookback,
            "horizons_bars": list(horizons),
            "bar_scales": ["M5", "H4", "D1"],
            "bar_construction": {
                "M5": "resample('5min', label='left', origin='start_day')",
                "H4": "4h buckets aligned to the " + format(args.fx_day_start, "02d")
                      + ":00 Beijing FX origin",
                "D1": "FX trading day starting " + format(args.fx_day_start, "02d")
                      + ":00 Beijing",
            },
            "lookahead": "none: signal and entry use bars <= i+1 only",
            "is_oos": {"split": "IS year < " + str(args.oos_year)
                                + ", OOS >= " + str(args.oos_year),
                       "note": "same split as exp01-exp04, not selected here"},
            "cost_pips_round_trip": args.cost_pips,
            "swap_per_night_sweep": list(SWAP_PER_NIGHT),
            "uncertainty": "calendar-month block bootstrap; signals treated as "
                           "clustered, not independent",
            "overlap": "measured on bar positions with a greedy non-overlapping subset",
            "fixed_not_scanned": ["lookback=12", "horizons={12,48}", "cost=1.5",
                                  "fx_day_start=6", "min_m1_ratio=0.5"],
        },
        "m5_reproducibility_anchor": {
            "note": "must reproduce the frozen Exp04 report; if it does not, "
                    "this run is invalid",
            "meta": anchor_meta,
            "stats": anchor,
        },
        "scales": {k: v for k, v in results.items()},
        "verdicts": verdicts,
        "verdict_rules": {
            "INSUFFICIENT EVIDENCE": "smallest cell n < " + str(MIN_N_FOR_VERDICT),
            "NOT ESTABLISHED": "not positive net of round-trip cost, OR inconsistent "
                               "sign across direction/horizon, OR IS/OOS sign mismatch, "
                               "OR best single year carries > 50% of "
                               "|yearly contribution|",
            "WORTH CONTINUING": "all of the above pass",
        },
        "caveats": [
            "Event study, not a strategy: no stops, targets, sizing or filters.",
            "Signals recur within the same move; windows overlap. Reported.",
            "Raw pips are not comparable across bar scales; use mean/sd.",
            "Round-trip cost is assumed; overnight financing is swept, not assumed.",
            "A surviving direction is still not a tradable strategy.",
        ],
    }
    rp = out_dir / "exp05_report.json"
    rp.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str))

    print("=" * W)
    print("events -> " + str(csv_path) + "  (" + format(len(all_ev), ",") + " rows)")
    print("report -> " + str(rp))
    print("=" * W)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
