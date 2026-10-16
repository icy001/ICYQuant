#!/usr/bin/env python3
"""EURUSD M1 audit before any intraday backtest.

Answers the questions that decide whether the later numbers mean anything:

1.  Duplicate timestamps (a doubled calendar would silently double every edge).
2.  Gaps / out-of-order rows.
3.  Timezone semantics of the stored `ts`. This is the decisive one. HistData
    documents its ASCII exports as EST *without* daylight saving, i.e. UTC-5 for
    the whole year. Internal consistency can be checked without trusting that
    claim: if timestamps carry no US daylight drift, the busiest clock hour of
    the year sits at the same hour in January and in July. A UTC-stamped file
    would show that hour moving by one between winter and summer.
4.  What the Beijing 09:00-10:00 window actually maps to in stored time -- this
    is the day-boundary trap: Beijing 09:00 is 20:00 of the PREVIOUS stored day.
5.  Whether that window is actually populated often enough to backtest.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
PARQUET = REPO / "artifacts/histdata_v9/parsed/eurusd_2000-2026_bars.parquet"

# HistData ASCII is documented as Eastern Standard Time with NO daylight saving:
# a constant UTC-5. Beijing is UTC+8, so Beijing = stored + 13h.
STORED_TO_UTC = pd.Timedelta(hours=5)
STORED_TO_BEIJING = pd.Timedelta(hours=13)
WINDOW_START = "09:00"
WINDOW_END = "10:00"   # exclusive


def pretty_head(s: pd.Series, n: int = 4) -> str:
    return ", ".join(f"{k}:{v}" for k, v in list(s.items())[:n])


def main() -> int:
    if not PARQUET.exists():
        print(f"MISSING {PARQUET}")
        return 1

    df = pd.read_parquet(PARQUET)
    ts = pd.to_datetime(df["ts"])
    df["ts"] = ts
    n = len(df)
    print("=" * 80)
    print("EURUSD M1 AUDIT (read-only)")
    print("=" * 80)
    print(f"file            : {PARQUET}")
    print(f"rows            : {n:,}")
    print(f"ts range        : {ts.min()}  ..  {ts.max()}")
    print(f"tz-aware        : {ts.dt.tz is not None}")

    # ---- 1. duplicated timestamps -------------------------------------
    dup_exact = int(ts.duplicated().sum())
    dup_full = int(df.duplicated(subset=["ts", "open", "high", "low", "close"]).sum())
    print("-" * 80)
    print(f"[1] duplicate timestamps        : {dup_exact:,}")
    print(f"    duplicate (ts + OHLC) rows  : {dup_full:,}")

    # ---- 2. ordering and gaps -----------------------------------------
    d = ts.diff().dropna()
    print("-" * 80)
    print(f"[2] out-of-order rows           : {int((d < pd.Timedelta(0)).sum()):,}")
    print(f"    median step                 : {d.median()}")
    print(f"    max gap                     : {d.max()}")
    print(f"    gaps > 1h count             : {int((d > pd.Timedelta(hours=1)).sum()):,}")
    print(f"    gaps > 24h count            : {int((d > pd.Timedelta(hours=24)).sum()):,}")

    # ---- 3. timezone semantics, read off the FX calendar itself ---------
    # The FX week opens ~17:00 New York on Sunday and closes ~17:00 New York on
    # Friday. Whichever clock those two events land on identifies the timestamp
    # convention; comparing winter with summer detects daylight saving.
    df["stored_date"] = ts.dt.floor("D")
    dow_num = ts.dt.dayofweek
    sun_first = df[dow_num == 6].groupby("stored_date")["ts"].min()
    fri_last = df[dow_num == 4].groupby("stored_date")["ts"].max()
    sun_h = (sun_first.dt.hour + sun_first.dt.minute / 60).round()
    fri_h = (fri_last.dt.hour + fri_last.dt.minute / 60).round()
    print("-" * 80)
    print("[3] timezone semantics, read off the FX calendar")
    print(f"    Sunday first bar, modal hour : {sun_h.mode().tolist()} "
          f"({(sun_h == sun_h.mode()[0]).mean():.1%} of weeks)")
    print(f"    Friday last bar,  modal hour : {fri_h.mode().tolist()} "
          f"({(fri_h == fri_h.mode()[0]).mean():.1%} of weeks)")
    winter = sun_h[sun_h.index.month.isin([1, 2])].mode().tolist()
    summer = sun_h[sun_h.index.month.isin([6, 7, 8])].mode().tolist()
    print(f"    Sunday open Jan-Feb vs Jun-Aug: {winter} vs {summer}")
    if winter and summer and winter == summer:
        print("    -> IDENTICAL winter and summer: no daylight-saving drift, so this is")
        print("       a fixed-offset clock. FX opening AND closing at stored 17:00 pins")
        print("       it to US Eastern time == HistData's documented fixed EST (UTC-5).")
        print("       => UTC = ts + 5h        BEIJING = ts + 13h")
    else:
        print("    -> hour MOVES with season: timestamps follow daylight saving.")

    # ---- 4. weekday footprint -----------------------------------------
    dow = ts.dt.dayofweek.map({0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu",
                               4: "Fri", 5: "Sat", 6: "Sun"})
    print("-" * 80)
    print("[4] rows by weekday")
    print(dow.value_counts().to_string())

    # ---- 5. stored-day bar counts -------------------------------------
    df["stored_date"] = ts.dt.floor("D")
    cnt = df.groupby("stored_date").size()
    print("-" * 80)
    print(f"[5] bars per stored calendar day: median={cnt.median():.0f} "
          f"p5={cnt.quantile(.05):.0f} p95={cnt.quantile(.95):.0f} max={cnt.max()}")

    # ---- 6. the day-boundary trap, made explicit -----------------------
    bt = ts + STORED_TO_BEIJING
    df["beijing_ts"] = bt
    df["beijing_date"] = bt.dt.floor("D")
    hm = bt.dt.strftime("%H:%M")
    in_win = (hm >= WINDOW_START) & (hm < WINDOW_END)
    print("-" * 80)
    print("[6] THE DAY-BOUNDARY TRAP")
    print(f"    Beijing 09:00 == stored-day {WINDOW_START} MINUS 13h == previous stored day 20:00")
    demo = df[in_win].iloc[0] if in_win.any() else None
    if demo is not None:
        print(f"    example row: stored={demo['ts']}  ->  Beijing={demo['beijing_ts']}")
        print(f"                 stored DATE={demo['stored_date'].date()}  "
              f"Beijing DATE={demo['beijing_date'].date()}   <-- differs")
    off_by = int((df.loc[in_win, "stored_date"] != df.loc[in_win, "beijing_date"]).sum())
    print(f"    rows in the 09:00-10:00 Beijing window whose stored-day differs "
          f"from its Beijing-day: {off_by:,} / {int(in_win.sum()):,}")
    print("    -> grouping the window by stored date silently attaches it to the WRONG day;")
    print("       the daily open must therefore be taken from the Beijing day, not the stored day.")

    # ---- 7. window coverage in Beijing time ----------------------------
    win_rows = df[in_win]
    per_day = win_rows.groupby("beijing_date").size()
    all_days = pd.date_range(per_day.index.min(), per_day.index.max(), freq="D")
    print("-" * 80)
    print("[7] Beijing 09:00-10:00 window coverage")
    print(f"    rows in window              : {len(win_rows):,}")
    print(f"    distinct Beijing days       : {len(per_day):,}")
    print(f"    calendar days spanned       : {len(all_days):,}")
    print(f"    rows per day  median={per_day.median():.0f} "
          f"min={per_day.min()} max={per_day.max()}  (60 of 60 minutes = full)")
    print(f"    days with >= 55 rows        : {int((per_day >= 55).sum()):,} "
          f"({(per_day >= 55).mean():.1%})")

    # ---- 8. FX day origin in Beijing time ------------------------------
    first_per_day = df.groupby("beijing_date")["beijing_ts"].min()
    fh = first_per_day.dt.hour
    print("-" * 80)
    print("[8] first bar of the Beijing day (FX day typically opens 06:00 Beijing"
          " = 17:00 New York close)")
    print(fh.value_counts().head(6).to_string())

    print("=" * 80)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
