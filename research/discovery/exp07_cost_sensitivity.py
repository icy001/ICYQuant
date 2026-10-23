#!/usr/bin/env python3
"""Exp07 -- Cost sensitivity: what execution cost does each strategy line need?

Why this exists
---------------
Exp04-06 all assumed a 1.5 pip round trip. That assumption, not the signal,
decided every verdict. Step 2 of the agreed plan is "confirm the real cost",
but the exact broker terms are not known yet, so this converts cost from an
assumption into an axis that can be read off a table once the real numbers
arrive.

Nothing new is estimated here. Every input is an existing artifact:
    exp04_events.csv  (M5 breakout, 257k events)
    exp05_events.csv  (H4/D1 breakout, 6.9k events)
    exp06_daily.csv   (D1 time-series momentum, daily legs)

Three different failure modes are separated explicitly, because they need
different answers:

  COST-BOUND      the signal is real and significant, the gross edge is just
                  smaller than the spread. A lower cost fixes it.
                  -> Exp04 M5 reversal (the only 8/8 IS-OOS-consistent effect)
  SIGNAL-BOUND    even at zero cost the Sharpe is far below any usable level.
                  A lower cost does NOT fix it.
                  -> Exp06 trend following
  UNSTABLE        the sign flips between IS and OOS, so no cost level makes it
                  dependable.
                  -> Exp05 D1/H4 breakout

Key definitions
---------------
    gross         mean directional return per trade, before cost, pips
    breakeven     the cost at which net expectancy hits exactly zero
    cost_for_S    the largest cost that still leaves annualised Sharpe >= S

For event studies Sharpe is annualised as (net_mean / sd) * sqrt(trades/year),
where sd is the per-trade standard deviation. Cost shifts the mean and leaves
sd unchanged, so the cost that buys a target Sharpe has a closed form.

Two n conventions are reported side by side because overlap matters:
    ALL         every valid signal (overlapping windows treated as separate
                trades is optimistic: overlapping trades cannot all be taken)
    NONOVERLAP  greedy non-overlapping subset (what a real book can hold)
The NONOVERLAP numbers are the honest ones for capacity; ALL is the ceiling.

For the reversal lines the traded direction is the OPPOSITE of Exp04's
breakout-direction return, so gross = -ret. Exp04 measured continuation, and
its negative mean is precisely the reversal edge.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
EXP04 = REPO / "artifacts/research/eurusd_breakout/exp04_events.csv"
EXP05 = REPO / "artifacts/research/eurusd_breakout_longer/exp05_events.csv"
EXP06 = REPO / "artifacts/research/eurusd_tsmom/exp06_daily.csv"
DEFAULT_OUT = REPO / "artifacts/research/cost_sensitivity"

COST_GRID = (0.0, 0.1, 0.2, 0.25, 0.3, 0.4, 0.5, 0.7, 1.0, 1.5)
SHARPE_TARGETS = (0.5, 1.0)
# reference execution regimes, only for orientation in the printed table
REALITY = (
    ("retail standard", 1.5),
    ("retail ECN", 0.6),
    ("good ECN + commission", 0.3),
    ("institutional", 0.15),
)
SWAP_SWEEP = (0.0, 0.3, 0.5, 1.0)
W = 128


def nonoverlap_mask(bars: np.ndarray, horizon: int) -> np.ndarray:
    """Greedy subset with at least `horizon` bars between kept signals."""
    keep = np.zeros(len(bars), dtype=bool)
    last = -(10 ** 15)
    for j, b in enumerate(bars):
        if b - last >= horizon:
            keep[j] = True
            last = b
    return keep


def years_between(ts: pd.Series) -> float:
    t = pd.to_datetime(ts)
    return max((t.max() - t.min()).days / 365.25, 1e-9)


def cell_stats(ret: np.ndarray, years: float) -> dict:
    """Breakeven cost and the Sharpe-vs-cost curve for one signal cell."""
    n = len(ret)
    if n < 30:
        return {"n": int(n), "insufficient": True}
    per_year = n / years
    mean = float(np.mean(ret))
    sd = float(np.std(ret, ddof=1))
    out = {
        "n": int(n),
        "trades_per_year": round(per_year, 1),
        "gross_mean_pips": round(mean, 4),
        "sd_pips": round(sd, 3),
        "breakeven_cost_pips": round(mean, 4),
        "years": round(years, 2),
    }
    if sd > 0:
        out["max_cost_for_sharpe"] = {
            str(S): round(mean - S * sd / np.sqrt(per_year), 4)
            for S in SHARPE_TARGETS
        }
        curve = {}
        for c in COST_GRID:
            net = mean - c
            curve[str(c)] = {
                "net_per_trade_pips": round(net, 4),
                "net_pips_per_year": round(net * per_year, 1),
                "sharpe_ann": round(net / sd * np.sqrt(per_year), 3),
            }
        out["cost_curve"] = curve
    return out


def analyze_exp04(path: Path) -> dict:
    """M5 breakout, traded as REVERSAL (gross = -ret)."""
    if not path.exists():
        return {}
    d = pd.read_csv(path)
    years_all = years_between(d["signal_bar"])
    res = {}
    for H in (12, 48):
        vcol, rcol = "valid_" + str(H), "ret_" + str(H)
        if vcol not in d.columns or rcol not in d.columns:
            continue
        for dd in ("up", "down"):
            s = d[(d["direction"] == dd) & (d[vcol].astype(bool))].dropna(subset=[rcol])
            if len(s) < 30:
                continue
            # reversal: Exp04's continuation return, negated
            g_all = -s[rcol].to_numpy(float)
            bars = s["bar_i"].to_numpy()
            order = np.argsort(bars, kind="stable")
            mask = nonoverlap_mask(bars[order], H)
            g_non = g_all[order][mask]
            y = years_between(s["signal_bar"])
            res["H" + str(H) + "_" + dd] = {
                "horizon_bars": H,
                "direction": dd,
                "traded_as": "reversal (gross = -ret, ret is breakout-direction)",
                "all_signals": cell_stats(g_all, y),
                "nonoverlap": cell_stats(g_non, y),
                "nonoverlap_share": round(float(mask.mean()), 4),
            }
    res["_years_span"] = round(years_all, 2)
    return res


def analyze_exp05(path: Path) -> dict:
    """H4/D1 breakout. Reported per cell as continuation, but flagged unstable
    because the sign differs across direction and horizon."""
    if not path.exists():
        return {}
    d = pd.read_csv(path)
    res = {}
    for scale in sorted(d["scale"].unique()):
        for H in (12, 48):
            vcol, rcol, ncol = ("valid_" + str(H), "ret_" + str(H), "nights_" + str(H))
            if vcol not in d.columns:
                continue
            for dd in ("up", "down"):
                s = d[(d["scale"] == scale) & (d["direction"] == dd)
                      & (d[vcol].astype(bool))].dropna(subset=[rcol])
                if len(s) < 30:
                    continue
                g = s[rcol].to_numpy(float)
                y = years_between(s["signal_bar"])
                st = cell_stats(g, y)
                if "insufficient" in st:
                    continue
                nights = float(s[ncol].mean()) if ncol in s.columns else None
                st["mean_nights"] = round(nights, 2) if nights is not None else None
                # cost that leaves zero net once financing is charged at 0.5/night
                if nights is not None:
                    st["breakeven_spread_after_swap_0_5"] = round(
                        st["gross_mean_pips"] - 0.5 * nights, 4)
                res[scale + "_H" + str(H) + "_" + dd] = st
    return res


def analyze_exp06(path: Path) -> dict:
    """Trend following: spread x swap surface. This one is signal-bound, so the
    surface is shown to prove that zero cost does not rescue it."""
    if not path.exists():
        return {}
    d = pd.read_csv(path)
    d = d[d["usable"].astype(bool)]
    if len(d) == 0:
        return {}
    res = {}
    for L in sorted(d["lookback"].unique()):
        s = d[d["lookback"] == L]
        years = years_between(s["date"])
        r_gross = s["r_gross"].to_numpy(float)
        held = s["held_overnight"].to_numpy(float)
        change = np.abs(s["pos_intraday"].to_numpy(int) - s["pos_overnight"].to_numpy(int))
        trades = int(change.sum())
        surface = {}
        for spread in (0.0, 0.25, 0.5, 0.75, 1.5):
            row = {}
            for swap in SWAP_SWEEP:
                r_net = r_gross - spread * change - swap * held
                sd = float(r_net.std(ddof=1))
                row[str(swap)] = {
                    "net_pips_total": round(float(r_net.sum()), 1),
                    "net_pips_per_year": round(float(r_net.sum()) / years, 1),
                    "sharpe_ann": round(float(r_net.mean()) / sd * np.sqrt(252), 3)
                    if sd > 0 else None,
                }
            surface[str(spread)] = row
        zero_sharpe = surface[str(0.0)][str(0.0)]["sharpe_ann"]
        res["L" + str(L)] = {
            "years": round(years, 2),
            "trades": trades,
            "gross_pips_total": round(float(r_gross.sum()), 1),
            "gross_pips_per_year": round(float(r_gross.sum()) / years, 1),
            "total_nights": round(float(held.sum()), 0),
            "zero_cost_sharpe": zero_sharpe,
            "surface": surface,
            "signal_bound": bool(zero_sharpe is not None and abs(zero_sharpe) < 0.5),
        }
    return res


def classify(exp04: dict, exp06: dict) -> dict:
    """Name the binding constraint for each line, so the answer is not
    'everything failed' but 'this is what has to change'."""
    out = {}
    for key, cell in exp04.items():
        if key.startswith("_"):
            continue
        non = cell.get("nonoverlap") or {}
        mc = non.get("max_cost_for_sharpe") or {}
        be = non.get("breakeven_cost_pips")
        if be is None:
            continue
        out[key] = {
            "binding": "COST" if be > 0 else "NO EDGE",
            "breakeven_cost_nonoverlap": be,
            "cost_needed_for_sharpe_0_5": mc.get("0.5"),
            "cost_needed_for_sharpe_1_0": mc.get("1.0"),
        }
    for key, cell in exp06.items():
        out[key] = {
            "binding": "SIGNAL" if cell.get("signal_bound") else "COST",
            "zero_cost_sharpe": cell.get("zero_cost_sharpe"),
            "note": "zero-cost Sharpe already below 0.5 -> cheaper execution "
                    "cannot rescue this line",
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Exp07 cost sensitivity across Exp04-06")
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT))
    args = ap.parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * W)
    print("Exp07 - COST SENSITIVITY: what execution cost does each line need?")
    print("=" * W)
    print("inputs : exp04_events.csv, exp05_events.csv, exp06_daily.csv (existing)")
    print("note   : gross = mean directional return per trade BEFORE cost, pips.")
    print("         breakeven = cost at which net expectancy is exactly zero.")
    print("         cost_for_S = largest cost still leaving annualised Sharpe >= S.")
    print("         NONOVERLAP is the honest capacity view; ALL is the ceiling.")

    exp04 = analyze_exp04(EXP04)
    exp05 = analyze_exp05(EXP05)
    exp06 = analyze_exp06(EXP06)

    # ---------------- M5 reversal: the only cost-bound line ----------------
    print("=" * W)
    print("[A] M5 BREAKOUT TRADED AS REVERSAL (Exp04) - cost-bound line")
    print("  " + format("cell", "<12") + format("n", ">9") + format("trades/yr", ">11")
          + format("gross_p", ">10") + format("sd_p", ">9")
          + format("breakeven", ">11") + format("cost@S0.5", ">11")
          + format("cost@S1.0", ">11"))
    for key, cell in exp04.items():
        if key.startswith("_"):
            continue
        for conv in ("all_signals", "nonoverlap"):
            st = cell.get(conv) or {}
            if st.get("insufficient") or "gross_mean_pips" not in st:
                continue
            mc = st.get("max_cost_for_sharpe") or {}
            label = key.replace("H12_", "1h_").replace("H48_", "4h_")
            label = label + ("" if conv == "all_signals" else "*")
            print("  " + format(label, "<12") + format(st["n"], ">9,")
                  + format(st["trades_per_year"], ">11,.0f")
                  + format(st["gross_mean_pips"], ">+10.4f")
                  + format(st["sd_pips"], ">9.2f")
                  + format(st["breakeven_cost_pips"], ">+11.4f")
                  + format(mc.get("0.5"), ">+11.4f")
                  + format(mc.get("1.0"), ">+11.4f"))
    print("  * = non-overlapping subset (what a real book can actually hold)")

    print("-" * W)
    print("  Sharpe-vs-cost curve, M5 reversal 1h up (ALL vs NONOVERLAP):")
    for conv, tag in (("all_signals", "ALL"), ("nonoverlap", "NONOVL")):
        st = (exp04.get("H12_up") or {}).get(conv) or {}
        curve = st.get("cost_curve") or {}
        if not curve:
            continue
        cells = []
        for c in ("0.0", "0.1", "0.2", "0.3", "0.5", "0.7", "1.5"):
            v = curve.get(c) or {}
            if v.get("sharpe_ann") is not None:
                cells.append(c + "p:" + format(v["sharpe_ann"], "+.2f"))
        print("    " + format(tag, "<8") + "  ".join(cells))

    print("-" * W)
    print("  Against real execution regimes (NONOVERLAP, computed at exact cost):")
    st = (exp04.get("H12_up") or {}).get("nonoverlap") or {}
    if st.get("gross_mean_pips") is not None and st.get("sd_pips"):
        m0, sd0, py0 = st["gross_mean_pips"], st["sd_pips"], st["trades_per_year"]
        for name, c in REALITY:
            net = m0 - c
            shr = net / sd0 * np.sqrt(py0)
            print("    " + format(name, "<26") + format(c, ">5") + "p  ->  Sharpe "
                  + format(shr, "+.3f")
                  + "   net " + format(net * py0, "+.1f") + "p/yr")

    # ---------------- H4/D1: unstable ----------------
    print("=" * W)
    print("[B] H4 / D1 BREAKOUT (Exp05) - sign flips across direction and horizon")
    print("  " + format("cell", "<16") + format("n", ">7") + format("gross_p", ">10")
          + format("breakeven", ">11") + format("nights", ">8")
          + format("be_spread@swap0.5", ">18"))
    for key, st in sorted(exp05.items()):
        if "gross_mean_pips" not in st:
            continue
        print("  " + format(key, "<16") + format(st["n"], ">7,")
              + format(st["gross_mean_pips"], ">+10.3f")
              + format(st["breakeven_cost_pips"], ">+11.3f")
              + format(st.get("mean_nights"), ">8")
              + format(st.get("breakeven_spread_after_swap_0_5"), ">+18.3f"))
    print("  reading: a positive breakeven does NOT mean tradable here - the sign")
    print("           differs between up and down and between 12 and 48 bars.")

    # ---------------- trend following: signal-bound ----------------
    print("=" * W)
    print("[C] D1 TREND FOLLOWING (Exp06) - signal-bound, cost is not the culprit")
    for L, st in sorted(exp06.items()):
        print("  " + L + ": years " + str(st["years"]) + " | trades " + str(st["trades"])
              + " | gross " + format(st["gross_pips_per_year"], "+.1f") + "p/yr"
              + " | total nights " + format(st["total_nights"], ",.0f"))
        print("      ZERO-COST Sharpe = " + str(st["zero_cost_sharpe"])
              + "   (gate is 0.5)")
        print("      " + format("spread/change", "<14")
              + "".join(format("swap=" + str(s), ">12") for s in SWAP_SWEEP))
        for spread, row in st["surface"].items():
            line = "      " + format(spread + "p", "<14")
            for s in SWAP_SWEEP:
                line = line + format(row[str(s)]["sharpe_ann"], ">12.3f")
            print(line)
        print("      -> even at spread=0 and swap=0 it stays far below the gate;")
        print("         a cheaper broker does not fix this line.")

    # ---------------- verdict table ----------------
    print("=" * W)
    print("[D] WHAT HAS TO CHANGE (binding constraint per line)")
    cls = classify(exp04, exp06)
    print("  " + format("line", "<14") + format("binding", ">12")
          + format("breakeven", ">12") + format("need for S=0.5", ">15")
          + "   action")
    for key, v in cls.items():
        be = v.get("breakeven_cost_nonoverlap")
        need = v.get("cost_needed_for_sharpe_0_5")
        if v["binding"] == "SIGNAL":
            print("  " + format(key, "<14") + format("SIGNAL", ">12")
                  + format("-", ">12") + format("-", ">15")
                  + "   zero-cost Sharpe " + str(v.get("zero_cost_sharpe"))
                  + " -> stronger signal needed, not cheaper fills")
        elif v["binding"] == "COST":
            print("  " + format(key, "<14") + format("COST", ">12")
                  + format(be, ">+12.3f") + format(need, ">+15.3f")
                  + "   needs round trip under " + format(need, ".2f") + "p for S=0.5")
        else:
            print("  " + format(key, "<14") + format("NO EDGE", ">12")
                  + format(be, ">+12.3f") + format("-", ">15")
                  + "   gross edge is negative even at zero cost")

    print("=" * W)
    print("[E] SCOPE")
    print("  * Pure re-analysis: no new signal, no parameter was chosen here.")
    print("  * Sharpe is per-line, fixed +1 unit, no stops/sizing; a real book is worse.")
    print("  * sd is held constant as cost varies, which is exact for a constant cost.")
    print("  * Overlapping signals cannot all be traded; NONOVERLAP is the capacity view.")
    print("  * Gross returns are pre-slippage. Slippage adds on top of every cost here.")

    rp = out_dir / "exp07_report.json"
    rp.write_text(json.dumps({
        "experiment": "exp07_cost_sensitivity",
        "type": "re-analysis of exp04-06 along the cost axis; no new signal",
        "question": "what round-trip cost does each strategy line need in order to "
                    "be viable, and is cost even the binding constraint?",
        "inputs": {"exp04": str(EXP04), "exp05": str(EXP05), "exp06": str(EXP06)},
        "method": {
            "cost_grid": list(COST_GRID),
            "sharpe_targets": list(SHARPE_TARGETS),
            "sharpe_annualisation": "(net_mean/sd)*sqrt(trades_per_year)",
            "sd_assumption": "constant in cost (exact for a constant per-trade cost)",
            "overlap_conventions": {
                "all_signals": "every valid signal; optimistic, windows overlap",
                "nonoverlap": "greedy subset >= horizon bars apart; capacity view",
            },
            "reversal_signing": "Exp04 ret is breakout-direction, so reversal "
                                "gross = -ret",
        },
        "reference_execution_regimes": {n: c for n, c in REALITY},
        "exp04_m5_reversal": exp04,
        "exp05_h4_d1_breakout": exp05,
        "exp06_trend_following": exp06,
        "binding_constraints": cls,
        "caveats": [
            "Re-analysis only; nothing was re-fitted.",
            "Pre-slippage; slippage is additional on every line.",
            "Per-line Sharpe with fixed +1 unit; a real book is worse.",
            "NONOVERLAP is the honest capacity view, ALL is the ceiling.",
        ],
    }, ensure_ascii=False, indent=2, default=str))
    print("report -> " + str(rp))
    print("=" * W)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
