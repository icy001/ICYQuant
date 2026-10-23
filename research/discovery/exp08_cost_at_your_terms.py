#!/usr/bin/env python3
"""Exp08 -- re-price every strategy line at the user's actual execution terms.

Stated terms
------------
    spread        0          ("点没有")
    commission    5 per lot  ("佣金1手5块")
    swap / carry  0          ("swap没有")

The commission unit is ambiguous, so every plausible reading is priced at once
rather than guessed:

    EURUSD 1 pip on 1 lot = 100,000 * 0.0001 = 10 USD
    round-trip pips = spread + (2 if charged per side else 1) * commission / 10

    $5 per side     -> 2 * 5.00 / 10 = 1.000 pip round trip
    $5 per round    -> 1 * 5.00 / 10 = 0.500 pip round trip
    CNY5 per side   -> 2 * 0.704 / 10 = 0.141 pip round trip
    CNY5 per round  -> 1 * 0.704 / 10 = 0.070 pip round trip

Zero swap is a material change, not a footnote: Exp05 (H4/D1) and Exp06
(trend following) both carry positions overnight and were previously penalised
at 0.5 pip per night. With carry at zero that entire penalty disappears, so
those lines are re-priced here rather than dismissed from Exp07's table.

No new signal is estimated and no parameter is chosen. This is a re-pricing of
exp04_events.csv, exp05_events.csv and exp06_daily.csv.
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

PIP_USD_PER_LOT = 10.0     # EURUSD: 1 pip on 1 standard lot = 10 USD
USDCNY = 7.1               # only used to show the CNY readings; flagged as an assumption
USER_SPREAD_PIPS = 0.0     # "点没有"
USER_SWAP_PIPS = 0.0       # "swap没有"
USER_COMMISSION = 5.0      # "1手5块"

SCENARIOS = (
    ("USD 5/side", USER_COMMISSION, True),
    ("USD 5/round", USER_COMMISSION, False),
    ("CNY 5/side", USER_COMMISSION / USDCNY, True),
    ("CNY 5/round", USER_COMMISSION / USDCNY, False),
)
GATE = 0.5
W = 118


def round_trip_pips(comm_usd: float, per_side: bool) -> float:
    """Round-trip cost in pips for one 1-lot trade."""
    sides = 2.0 if per_side else 1.0
    return USER_SPREAD_PIPS + sides * comm_usd / PIP_USD_PER_LOT


def nonoverlap_mask(bars: np.ndarray, horizon: int) -> np.ndarray:
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


def sharpe(net: np.ndarray, per_year: float) -> float:
    sd = float(np.std(net, ddof=1))
    return float(net.mean()) / sd * np.sqrt(per_year) if sd > 0 else float("nan")


def load_event_cells(path: Path, traded_as_reversal: bool) -> dict:
    """Return {cell: (gross_by_scenario_ready_array, years, mean_nights)} for
    the NON-OVERLAPPING subset, which is the capacity-honest convention."""
    d = pd.read_csv(path)
    out = {}
    groups = []
    if "scale" in d.columns:
        for sc in sorted(d["scale"].unique()):
            for H in (12, 48):
                for dd in ("up", "down"):
                    groups.append((d[d["scale"] == sc], sc, H, dd))
    else:
        for H in (12, 48):
            for dd in ("up", "down"):
                groups.append((d, "M5", H, dd))
    for base, tag, H, dd in groups:
        vcol, rcol, ncol = "valid_" + str(H), "ret_" + str(H), "nights_" + str(H)
        if vcol not in base.columns:
            continue
        s = base[(base["direction"] == dd) & (base[vcol].astype(bool))].dropna(subset=[rcol])
        if len(s) < 30:
            continue
        g = s[rcol].to_numpy(float)
        if traded_as_reversal:
            g = -g                      # Exp04: trade the reversal, not continuation
        bars = s["bar_i"].to_numpy()
        order = np.argsort(bars, kind="stable")
        g = g[order][nonoverlap_mask(bars[order], H)]
        nights = float(s[ncol].mean()) if ncol in s.columns else 0.0
        out[tag + "_H" + str(H) + "_" + dd] = (g, years_between(s["signal_bar"]), nights)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Exp08 re-pricing of exp04-06 at the user's execution terms")
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT))
    args = ap.parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * W)
    print("Exp08 - RE-PRICING AT YOUR TERMS   spread=0   commission=5/lot   swap=0")
    print("=" * W)
    print("conversion: EURUSD 1 pip on 1 lot = 100,000 * 0.0001 = 10 USD")
    print("            round-trip pips = spread + (2 if per side else 1) * comm / 10")
    print("zero swap removes the overnight penalty that previously hit H4/D1 and trend")
    print("following; those lines are therefore re-priced, not inherited from Exp07.")
    print("")
    print("  " + format("reading", "<14") + format("round-trip cost", ">18")
          + format("per-change cost", ">18"))
    per_change = {}
    for name, comm, per_side in SCENARIOS:
        rt = round_trip_pips(comm, per_side)
        pc = round_trip_pips(comm, per_side) / 2.0   # split across open and close
        per_change[name] = pc
        print("  " + format(name, "<14") + format(rt, ">15.4f") + "p"
              + format(pc, ">15.4f") + "p")

    # ---------------- event-study lines ----------------
    cells04 = load_event_cells(EXP04, traded_as_reversal=True) if EXP04.exists() else {}
    cells05 = load_event_cells(EXP05, traded_as_reversal=False) if EXP05.exists() else {}

    print("=" * W)
    print("[A] M5 REVERSAL 1h/4h (Exp04) - non-overlapping subset")
    print("  " + format("cell", "<14") + format("trades/yr", ">10")
          + format("gross_p", ">10") + format("zero-cost SR", ">13")
          + "".join(format(n, ">14") for n, _, _ in SCENARIOS))
    print("  " + " " * 47 + "".join(format("SR @" + format(round_trip_pips(c, s), ".2f") + "p", ">14")
                                    for _, c, s in SCENARIOS))
    rows04 = {}
    for key, (g, years, _n) in sorted(cells04.items()):
        py = len(g) / years
        sr0 = sharpe(g, py)
        line = "  " + format(key, "<14") + format(py, ">10,.0f") \
            + format(float(g.mean()), ">+10.4f") + format(sr0, ">13.3f")
        row = {"gross_pips": round(float(g.mean()), 4), "trades_per_year": round(py, 1),
               "zero_cost_sharpe": round(sr0, 3), "by_scenario": {}}
        for name, comm, per_side in SCENARIOS:
            c = round_trip_pips(comm, per_side)
            sr = sharpe(g - c, py)
            row["by_scenario"][name] = {
                "cost_pips": round(c, 4), "sharpe": round(sr, 3),
                "net_pips_per_year": round((g.mean() - c) * py, 1)}
            line = line + format(sr, ">14.3f")
        rows04[key] = row
        print(line)

    print("-" * W)
    print("[B] H4 / D1 BREAKOUT (Exp05) - continuation, swap now 0")
    print("  " + format("cell", "<16") + format("trades/yr", ">10")
          + format("gross_p", ">10") + format("nights", ">8")
          + "".join(format(n, ">14") for n, _, _ in SCENARIOS))
    rows05 = {}
    for key, (g, years, nights) in sorted(cells05.items()):
        py = len(g) / years
        line = "  " + format(key, "<16") + format(py, ">10,.0f") \
            + format(float(g.mean()), ">+10.3f") + format(nights, ">8.1f")
        row = {"gross_pips": round(float(g.mean()), 4), "trades_per_year": round(py, 1),
               "mean_nights": round(nights, 2), "by_scenario": {}}
        for name, comm, per_side in SCENARIOS:
            c = round_trip_pips(comm, per_side) + USER_SWAP_PIPS * nights
            sr = sharpe(g - c, py)
            row["by_scenario"][name] = {
                "cost_pips": round(c, 4), "sharpe": round(sr, 3),
                "net_pips_per_year": round((g.mean() - c) * py, 1)}
            line = line + format(sr, ">14.3f")
        rows05[key] = row
        print(line)

    # ---------------- trend following ----------------
    print("=" * W)
    print("[C] D1 TREND FOLLOWING (Exp06) - swap now 0")
    rows06 = {}
    if EXP06.exists():
        d = pd.read_csv(EXP06)
        d = d[d["usable"].astype(bool)]
        for L in sorted(d["lookback"].unique()):
            s = d[d["lookback"] == L]
            years = years_between(s["date"])
            rg = s["r_gross"].to_numpy(float)
            held = s["held_overnight"].to_numpy(float)
            changes = np.abs(s["pos_intraday"].to_numpy(int) - s["pos_overnight"].to_numpy(int))
            line = "  " + format("L" + str(L), "<16") + format(len(s) / 252, ">10,.0f") \
                + format(rg.sum() / years, ">+10.1f") + format(held.mean() * 252, ">8.0f")
            row = {"gross_pips_per_year": round(float(rg.sum()) / years, 1),
                   "trades": int(changes.sum()), "by_scenario": {}}
            for name, comm, per_side in SCENARIOS:
                rnet = rg - per_change[name] * changes - USER_SWAP_PIPS * held
                sr = float(rnet.mean()) / float(rnet.std(ddof=1)) * np.sqrt(252)
                row["by_scenario"][name] = {
                    "cost_per_change_pips": round(per_change[name], 4),
                    "sharpe": round(sr, 3),
                    "net_pips_per_year": round(float(rnet.sum()) / years, 1)}
                line = line + format(sr, ">14.3f")
            rows06["L" + str(L)] = row
            print(line)

    # ---------------- verdict ----------------
    print("=" * W)
    print("[D] VERDICT AT YOUR TERMS (gate: Sharpe >= " + str(GATE) + " per line)")
    for name, _, _ in SCENARIOS:
        alive = []
        for k, r in rows04.items():
            v = r["by_scenario"][name]
            if v["sharpe"] >= GATE:
                alive.append(k + " (SR " + format(v["sharpe"], ".2f") + ")")
        for k, r in rows05.items():
            v = r["by_scenario"][name]
            if v["sharpe"] >= GATE:
                alive.append(k + " (SR " + format(v["sharpe"], ".2f") + ")")
        for k, r in rows06.items():
            v = r["by_scenario"][name]
            if v["sharpe"] >= GATE:
                alive.append(k + " (SR " + format(v["sharpe"], ".2f") + ")")
        tag = name + "  (" + format(round_trip_pips(
            dict((n, c) for n, c, _ in SCENARIOS)[name],
            dict((n, s) for n, _, s in SCENARIOS)[name]), ".2f") + "p round trip)"
        if alive:
            print("  " + format(tag, "<34") + " ALIVE: " + ", ".join(alive))
        else:
            print("  " + format(tag, "<34") + " none clears the gate")

    print("=" * W)
    print("[E] SCOPE")
    print("  * Re-pricing only; no signal re-estimated, no parameter chosen.")
    print("  * Non-overlapping subset for event studies: the capacity-honest view.")
    print("  * Costs are pre-slippage; slippage is additional on every line.")
    print("  * Sharpe is per line at fixed +1 unit, no stops or sizing.")
    print("  * USDCNY = " + str(USDCNY) + " is an assumption used only to display the")
    print("    CNY readings; it does not affect any USD reading.")
    print("  * swap = 0 means no overnight charge AND no overnight credit. A real")
    print("    account usually pays or receives carry; see the carry work for that.")

    rp = out_dir / "exp08_report.json"
    rp.write_text(json.dumps({
        "experiment": "exp08_cost_at_your_terms",
        "type": "re-pricing of exp04-06 at stated execution terms; no new signal",
        "stated_terms": {
            "spread_pips": USER_SPREAD_PIPS,
            "commission_per_lot": USER_COMMISSION,
            "swap_pips_per_night": USER_SWAP_PIPS,
            "commission_unit_ambiguous": True,
        },
        "conversion": {
            "pip_usd_per_lot": PIP_USD_PER_LOT,
            "formula": "round_trip_pips = spread + (2 if per_side else 1) * comm / 10",
            "usdcny_assumption": USDCNY,
        },
        "scenarios": {n: {"commission_usd": c, "per_side": s,
                          "round_trip_pips": round(round_trip_pips(c, s), 4)}
                      for n, c, s in SCENARIOS},
        "effect_of_zero_swap": "removes the overnight penalty previously charged to "
                               "Exp05 H4/D1 and Exp06; both re-priced rather than "
                               "inherited from Exp07",
        "gate_sharpe": GATE,
        "exp04_m5_reversal": rows04,
        "exp05_h4_d1_breakout": rows05,
        "exp06_trend_following": rows06,
        "caveats": [
            "Commission unit is ambiguous; four readings are priced, not guessed.",
            "Non-overlapping subset is the capacity-honest convention.",
            "Pre-slippage; slippage adds on top of every line.",
            "Per-line Sharpe at fixed +1 unit, no stops or sizing.",
        ],
    }, ensure_ascii=False, indent=2, default=str))
    print("report -> " + str(rp))
    print("=" * W)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
