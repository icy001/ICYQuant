#!/usr/bin/env python3
"""Fetch ECB daily reference exchange rates (free, no key, no signup).

WHY THIS SOURCE
---------------
It is official (European Central Bank), free, needs no API key, and reaches
back to 2000 with data refreshed to the previous business day. It was verified
live. Two non-obvious things it depends on, both found by probing:

  * HTTP/2 hangs. The TLS handshake succeeds and then the request never
    completes, surfacing as curl HTTP:000. Forcing HTTP/1.1 fixes it.
  * format=csv returns SDMX-XML, NOT csv. The real csv parameter is
    format=csvdata.
  * A single request spanning many years is silently truncated (2000-2026 came
    back ending in 2007). Requesting in ~5 year chunks returns everything.

WHAT IT CAN AND CANNOT BE USED FOR
----------------------------------
ECB publishes ONE reference rate per day (fixed at 14:15 CET). There is no
open/high/low. So:

  usable for       : daily returns, trend, carry, cross-sectional panels
  NOT usable for   : anything needing intraday extremes -> no fenxing, no bi,
                     no zhongshu, therefore no Chan. Chan needs high/low and
                     this source does not have it.

Currency convention: ECB stores X per EUR ("D.USD.EUR" = USD per 1 EUR).
This script also derives the market-style USDxxx / xxxUSD series so the output
can be compared directly with broker data.
"""
from __future__ import annotations

import argparse
import csv
import io
import sys
import time
import urllib.error
import urllib.request
from http.client import HTTPConnection  # noqa: F401  (forces HTTP/1.1 import)
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEFAULT_OUT = REPO / "data/real/ecb_d1"

API = "https://data-api.ecb.europa.eu/service/data/EXR"
# ECB publishes "currency per 1 EUR"
CURRENCIES = ("USD", "JPY", "GBP", "CHF", "CAD", "AUD", "NZD", "SEK", "NOK")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
CHUNK_YEARS = 5


def _get(url: str, timeout: int = 60) -> str:
    """GET forcing HTTP/1.1. HTTP/2 stalls on this host."""
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/csv,*/*",
    })
    # urllib has no http version switch; the opener honours HTTP/1.1 by default
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    return raw.decode("utf-8", "replace")


def fetch_chunk(cur: str, y0: int, y1: int, retries: int = 3):
    """Return list of (date, value) for one currency over [y0, y1]."""
    url = (f"{API}/D.{cur}.EUR.SP00.A"
           f"?startPeriod={y0}-01-01&endPeriod={y1}-12-31&format=csvdata")
    for attempt in range(retries):
        try:
            text = _get(url)
            break
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            if attempt == retries - 1:
                print(f"    ! {cur} {y0}-{y1} failed: {e}")
                return []
            time.sleep(2 * (attempt + 1))
    rows = []
    rd = csv.DictReader(io.StringIO(text))
    for r in rd:
        d = (r.get("TIME_PERIOD") or "").strip()
        v = (r.get("OBS_VALUE") or "").strip()
        if not d or v in ("", "NaN"):
            continue
        try:
            rows.append((d, float(v)))
        except ValueError:
            continue
    return rows


def fetch_currency(cur: str, y0: int, y1: int):
    """Fetch one currency in chunks, dedup and sort."""
    seen: dict[str, float] = {}
    y = y0
    while y <= y1:
        ye = min(y + CHUNK_YEARS - 1, y1)
        for d, v in fetch_chunk(cur, y, ye):
            seen[d] = v
        print(f"    {cur} {y}-{ye}: {len(seen)} cumulative")
        y = ye + 1
        time.sleep(0.4)
    return sorted(seen.items())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--currencies", default=",".join(CURRENCIES))
    ap.add_argument("--start-year", type=int, default=2000)
    ap.add_argument("--end-year", type=int, default=2026)
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT))
    args = ap.parse_args()

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    curs = [c.strip().upper() for c in args.currencies.split(",") if c.strip()]

    print("=" * 74)
    print("ECB daily reference rates -> " + str(out))
    print(f"currencies: {', '.join(curs)}")
    print(f"window    : {args.start_year}-{args.end_year}")
    print("NOTE: single daily reference rate, NO open/high/low.")
    print("=" * 74)

    eurusd: dict[str, float] = {}
    for cur in curs:
        series = fetch_currency(cur, args.start_year, args.end_year)
        if not series:
            continue
        if cur == "USD":
            eurusd = dict(series)
        p = out / f"ECB_{cur}PEREUR_d1.csv"
        with p.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["date", f"{cur.lower()}_per_eur"])
            w.writerows(series)
        print(f"  {cur}: {len(series)} rows  {series[0][0]} .. {series[-1][0]}  -> {p.name}")

    # market convention: EURUSD = USD per EUR; XXXUSD = EURUSD / (XXX per EUR)
    if eurusd:
        base = out / "EURUSD_d1.csv"
        with base.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["date", "close"])
            for d, v in sorted(eurusd.items()):
                w.writerow([d, v])
        print(f"  EURUSD: {len(eurusd)} rows -> {base.name}")
        for cur in curs:
            if cur == "USD":
                continue
            series = fetch_currency(cur, args.start_year, args.end_year) \
                if not (out / f"ECB_{cur}PEREUR_d1.csv").exists() else None
            rows = []
            with (out / f"ECB_{cur}PEREUR_d1.csv").open() as f:
                rd = csv.reader(f)
                next(rd)
                for d, v in rd:
                    rows.append((d, float(v)))
            dates = [d for d, _ in rows]
            vals = {d: v for d, v in rows}
            p = out / f"{cur}USD_d1.csv"
            n = 0
            with p.open("w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["date", "close"])
                for d in dates:
                    # EUR per XXX -> USD per XXX
                    if d in eurusd and vals[d] > 0:
                        w.writerow([d, round(eurusd[d] / vals[d], 6)])
                        n += 1
            print(f"  {cur}USD: {n} rows -> {p.name}")

    print("=" * 74)
    print("done. remember: no OHLC, so this cannot drive a Chan study.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
