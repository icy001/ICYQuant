#!/usr/bin/env python3
"""Download HistData "Generic ASCII" M1 data for arbitrary currency pairs.

WHY THIS EXISTS
---------------
HistData does not expose static zip URLs. Each zip is guarded by a per
(currency pair, month) token "tk" that is embedded in that month's landing
page and POSTed to /get.php. Three facts this relies on, all verified by
probing the live site:

  1. The token lives in  <input type="hidden" name="tk" value="...">  on
     /download-free-forex-historical-data/?/ascii/1-minute-bar-quotes/
     {pair}/{year}/{month}
  2. The token is bound to that ONE (pair, month). Reusing it for a different
     month or a different pair returns an empty 200 response.
  3. When a month has no data the token is present but EMPTY. That doubles as
     the availability probe, so we never waste requests downloading nothing.

The POST must carry Content-Type: application/x-www-form-urlencoded. Without
it the request fails at the connection level (curl reports HTTP:000), which is
the non-obvious part.

Output layout matches what is already in the repo:
    data/real/histdata/HISTDATA_COM_ASCII_{PAIR}_M1{YEAR}/DAT_ASCII_{PAIR}_M1_{YEAR}{MM}.csv

  probe only, then download:
    python3 scripts/histdata/download_ascii_m1.py --probe-only
    python3 scripts/histdata/download_ascii_m1.py --pairs USDJPY
"""
from __future__ import annotations

import argparse
import io
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEFAULT_DEST = REPO / "data/real/histdata"

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
BASE = "https://www.histdata.com"
TOKEN_RE = re.compile(r'name="tk"[^>]*value="([0-9a-f]{32})"')

G10 = ("EURUSD", "GBPUSD", "USDJPY", "USDCHF", "USDCAD",
       "AUDUSD", "NZDUSD", "EURGBP", "EURJPY", "GBPJPY",
       "AUDJPY", "EURAUD")


def landing_url(pair: str, year: int, month: int) -> str:
    return (f"{BASE}/download-free-forex-historical-data/"
            f"?/ascii/1-minute-bar-quotes/{pair.lower()}/{year}/{month:02d}")


def _get(url: str, timeout: int = 30, referer: str | None = None) -> str:
    headers = {"User-Agent": UA}
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def _post_zip(pair: str, year: int, month: int, tk: str, timeout: int = 90) -> bytes:
    body = urllib.parse.urlencode({
        "tk": tk,
        "date": str(year),
        "datemonth": f"{year}{month:02d}",
        "platform": "ASCII",
        "timeframe": "M1",
        "fxpair": pair,
    }).encode("ascii")
    req = urllib.request.Request(
        BASE + "/get.php",
        data=body,
        headers={
            "User-Agent": UA,
            # without this the request dies at connection level
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": landing_url(pair, year, month),
            "Origin": BASE,
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def fetch_token(pair: str, year: int, month: int, retries: int = 2):
    """Return the per-(pair, month) token, or None if that month has no data."""
    url = landing_url(pair, year, month)
    for attempt in range(retries + 1):
        try:
            html = _get(url)
            m = TOKEN_RE.search(html)
            if m:
                return m.group(1)
            # token present but empty -> month genuinely has no data
            if 'name="tk"' in html:
                return None
        except (urllib.error.URLError, TimeoutError, OSError):
            pass
        if attempt < retries:
            time.sleep(1.5 * (attempt + 1))
    return None


def target_csv(dest: Path, pair: str, year: int, month: int) -> Path:
    d = dest / f"HISTDATA_COM_ASCII_{pair}_M1{year}"
    return d / f"DAT_ASCII_{pair}_M1_{year}{month:02d}.csv"


def download_one(pair, year, month, dest: Path, delay: float = 0.0):
    """Download one month. Returns (status, detail)."""
    out = target_csv(dest, pair, year, month)
    if out.exists() and out.stat().st_size > 0:
        return ("skip", f"{pair} {year}-{month:02d} already present")

    tk = fetch_token(pair, year, month)
    if tk is None:
        return ("nodata", f"{pair} {year}-{month:02d} no data on server")
    if delay:
        time.sleep(delay)
    try:
        blob = _post_zip(pair, year, month, tk)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return ("error", f"{pair} {year}-{month:02d} POST failed: {e}")
    if len(blob) < 100 or blob[:2] != b"PK":
        return ("error", f"{pair} {year}-{month:02d} not a zip ({len(blob)} B)")

    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            names = [n for n in z.namelist()
                     if n.upper().endswith(".CSV") and not n.startswith("__")]
            if not names:
                return ("error", f"{pair} {year}-{month:02d} zip has no CSV")
            payload = z.read(names[0])
    except zipfile.BadZipFile:
        return ("error", f"{pair} {year}-{month:02d} bad zip")

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(payload)
    rows = payload.count(b"\n")
    return ("ok", f"{pair} {year}-{month:02d}  {len(payload)/1024:.0f} KB  {rows} rows")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pairs", default="USDJPY",
                    help="comma separated, e.g. USDJPY,GBPUSD")
    ap.add_argument("--start-year", type=int, default=2000)
    ap.add_argument("--end-year", type=int, default=2026)
    ap.add_argument("--dest", default=str(DEFAULT_DEST))
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--delay", type=float, default=0.3,
                    help="politeness delay per POST, seconds")
    ap.add_argument("--probe-only", action="store_true",
                    help="only report which months have data, download nothing")
    args = ap.parse_args()

    pairs = [p.strip().upper() for p in args.pairs.split(",") if p.strip()]
    dest = Path(args.dest)
    months = [(y, m) for y in range(args.start_year, args.end_year + 1)
              for m in range(1, 13)]

    print("=" * 78)
    print("HistData Generic ASCII M1 downloader")
    print("=" * 78)
    print("pairs    : " + ", ".join(pairs))
    print("window   : " + str(args.start_year) + "-" + str(args.end_year)
          + "  (" + str(len(months)) + " months each)")
    print("dest     : " + str(dest))
    print("mode     : " + ("PROBE ONLY" if args.probe_only else "download"))
    print("-" * 78)

    jobs = [(p, y, m) for p in pairs for (y, m) in months]

    if args.probe_only:
        # probe: one GET per month, parallel
        found: dict[str, list] = {p: [] for p in pairs}
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = {ex.submit(fetch_token, p, y, m): (p, y, m)
                    for (p, y, m) in jobs}
            done = 0
            for fut in as_completed(futs):
                p, y, m = futs[fut]
                done += 1
                if fut.result() is not None:
                    found[p].append((y, m))
                if done % 60 == 0:
                    print("  probed " + str(done) + "/" + str(len(jobs)) + " ...")
        print("-" * 78)
        for p in pairs:
            ys = sorted({y for (y, m) in found[p]})
            if ys:
                print(p + ": " + str(len(found[p])) + " months available, "
                      + str(ys[0]) + " .. " + str(ys[-1]))
                missing = [y for y in range(ys[0], ys[-1] + 1) if y not in ys]
                if missing:
                    print("    missing years: " + ", ".join(map(str, missing)))
            else:
                print(p + ": NO DATA in this window")
        return 0

    counts = {"ok": 0, "skip": 0, "nodata": 0, "error": 0}
    errors = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(download_one, p, y, m, dest, args.delay): (p, y, m)
                for (p, y, m) in jobs}
        done = 0
        for fut in as_completed(futs):
            status, detail = fut.result()
            counts[status] = counts.get(status, 0) + 1
            if status == "error":
                errors.append(detail)
            elif status == "ok":
                print("  " + detail)
            done += 1
            if done % 24 == 0:
                print("  ... " + str(done) + "/" + str(len(jobs))
                      + "  ok=" + str(counts["ok"])
                      + " skip=" + str(counts["skip"])
                      + " nodata=" + str(counts["nodata"]))

    print("-" * 78)
    print("downloaded " + str(counts["ok"]) + "   skipped " + str(counts["skip"])
          + "   no-data " + str(counts["nodata"]) + "   errors " + str(counts["error"]))
    for e in errors[:15]:
        print("  ERR " + e)
    print("=" * 78)
    return 0 if counts["error"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
