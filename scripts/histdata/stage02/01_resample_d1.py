#!/usr/bin/env python3
"""Stage 02, Script 1: resample the accepted M1 parquet to D1 bars + EDA.

Reads:   artifacts/histdata_v9/parsed/eurusd_2000-2026_bars.parquet
Writes:  artifacts/histdata_v9/derived/eurusd_2000-2026_d1.parquet
         artifacts/histdata_v9/derived/eurusd_d1_eda.json
Rules:   read-only on raw data, no git ops, streaming events to stdout.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_M1 = REPO_ROOT / "artifacts/histdata_v9/parsed/eurusd_2000-2026_bars.parquet"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts/histdata_v9/derived"


def emit(obj: dict) -> None:
    obj["ts"] = datetime.now(timezone.utc).isoformat()
    print(json.dumps(obj, ensure_ascii=False, default=str), flush=True)


def main(argv: list | None = None) -> int:
    p = argparse.ArgumentParser(description="M1 -> D1 resample + EDA")
    p.add_argument("--m1", default=str(DEFAULT_M1))
    p.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = p.parse_args(argv if argv is not None else sys.argv[1:])

    m1_path = Path(args.m1)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    emit({"event": "start", "script": "stage02_01_resample_d1",
          "input": str(m1_path), "exists": m1_path.exists()})
    if not m1_path.exists():
        emit({"event": "error", "code": "m1_missing"})
        return 5

    df = pd.read_parquet(m1_path)
    emit({"event": "m1_loaded", "rows": len(df),
          "ts_min": df["ts"].min(), "ts_max": df["ts"].max()})

    # --- spike quarantine: isolated M1 jumps > 10% vs BOTH neighbors -------
    # (v9 Stage 01 gates check OHLC self-consistency, not cross-bar outliers;
    #  a bar whose close deviates >10% from prev AND next close is a bad
    #  tick, e.g. the 2001-06-07 1965.0001 glitch in the histdata 2001 pack.)
    prev_close = df["close"].shift(1)
    next_close = df["close"].shift(-1)
    dev_prev = (df["close"] - prev_close).abs() / prev_close.abs()
    dev_next = (df["close"] - next_close).abs() / next_close.abs()
    spike_mask = (dev_prev > 0.10) & (dev_next > 0.10)
    spike_count = int(spike_mask.sum())
    if spike_count:
        spike_path = out_dir / "eurusd_spike_bars.jsonl"
        spike_path.write_text(
            "\n".join(json.dumps(r, default=str)
                      for r in df[spike_mask].to_dict("records")) + "\n",
            encoding="utf-8")
        emit({"event": "spikes_quarantined", "count": spike_count,
              "path": str(spike_path)})
        df = df[~spike_mask].reset_index(drop=True)
    else:
        emit({"event": "spikes_quarantined", "count": 0})

    # --- D1 aggregation: calendar-day grouping on naive timestamps ---------
    d1 = (df.assign(day=df["ts"].dt.normalize())
            .groupby("day", sort=True)
            .agg(open=("open", "first"), high=("high", "max"),
                 low=("low", "min"), close=("close", "last"),
                 volume=("volume", "sum"), bars=("close", "size"))
            .reset_index()
            .rename(columns={"day": "date"}))
    emit({"event": "d1_built", "days": len(d1)})

    # --- D1 invariants (mirrors Stage 01 G06 semantics) -------------------
    oc_max = d1[["open", "close"]].max(axis=1)
    oc_min = d1[["open", "close"]].min(axis=1)
    bad_ohlc = int(((d1["high"] < oc_max) | (d1["low"] > oc_min)).sum())
    bad_price = int((d1[["open", "high", "low", "close"]] <= 0).any(axis=1).sum())
    emit({"event": "d1_invariants", "bad_ohlc": bad_ohlc,
          "bad_price": bad_price})
    if bad_ohlc or bad_price:
        emit({"event": "error", "code": "d1_invariant_violation",
              "bad_ohlc": bad_ohlc, "bad_price": bad_price})
        return 6

    # --- write + roundtrip -------------------------------------------------
    d1_path = out_dir / "eurusd_2000-2026_d1.parquet"
    d1.to_parquet(d1_path, index=False)
    back = pd.read_parquet(d1_path)
    roundtrip_ok = (len(back) == len(d1)
                    and bool((back["close"] == d1["close"]).all())
                    and bool((back["date"] == d1["date"]).all()))
    emit({"event": "d1_written", "path": str(d1_path),
          "rows": len(d1), "bytes": d1_path.stat().st_size,
          "roundtrip_ok": roundtrip_ok})
    if not roundtrip_ok:
        return 7

    # --- EDA ----------------------------------------------------------------
    years = d1["date"].dt.year
    per_year = []
    for y, g in d1.groupby(years):
        per_year.append({
            "year": int(y), "days": len(g), "bars": int(g["bars"].sum()),
            "min_low": float(g["low"].min()), "max_high": float(g["high"].max()),
            "first_date": g["date"].min().date().isoformat(),
            "last_date": g["date"].max().date().isoformat(),
        })

    weekday_counts = d1["date"].dt.dayofweek.value_counts().sort_index()
    weekday_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    weekday_dist = {weekday_names[i]: int(weekday_counts.get(i, 0))
                    for i in range(7)}

    # first-bar clock time of each day (session anchoring evidence)
    first_bar_time = (df.assign(day=df["ts"].dt.normalize())
                        .groupby("day")["ts"].min().dt.strftime("%H:%M"))
    first_time_top = first_bar_time.value_counts().head(5).to_dict()

    # largest calendar gap between consecutive trading days
    gaps = d1["date"].diff().dt.days
    max_gap = int(gaps.max())
    max_gap_at = d1["date"].iloc[int(gaps.idxmax())].date().isoformat() \
        if len(d1) > 1 else None

    bars_per_day = d1["bars"]
    eda = {
        "source": str(m1_path), "m1_rows": len(df), "d1_rows": len(d1),
        "spike_bars_quarantined": spike_count,
        "date_min": d1["date"].min().date().isoformat(),
        "date_max": d1["date"].max().date().isoformat(),
        "volume_all_zero": bool((d1["volume"] == 0).all()),
        "bars_per_day": {"min": int(bars_per_day.min()),
                         "median": float(bars_per_day.median()),
                         "max": int(bars_per_day.max())},
        "weekday_distribution": weekday_dist,
        "first_bar_time_top5": first_time_top,
        "max_calendar_gap_days": max_gap, "max_gap_at": max_gap_at,
        "per_year": per_year,
        "price_min": float(d1["low"].min()), "price_max": float(d1["high"].max()),
    }
    eda_path = out_dir / "eurusd_d1_eda.json"
    eda_path.write_text(json.dumps(eda, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    emit({"event": "eda_written", "path": str(eda_path)})

    emit({"event": "end", "ok": True, "exit_code": 0,
          "d1_path": str(d1_path), "eda_path": str(eda_path),
          "d1_rows": len(d1)})
    return 0


if __name__ == "__main__":
    sys.exit(main())
