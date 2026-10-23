"""Fetch and clean the World Bank "Pink Sheet" monthly commodity prices.

WHY THIS SOURCE
---------------
Every other market-data source reachable from this machine is unusable for a
multi-asset study: Yahoo returns 403, Stooq (.com and .pl) serves a SHA-256
proof-of-work JavaScript challenge, Binance/Coinbase are blocked at the
network layer, FRED and Dukascopy time out, and HistData's free tier only
serves a rolling ~22-month window.

The World Bank Commodity Markets "Pink Sheet" is the exception:

    free, no API key, official, monthly, ~70 commodities, 1960 -> present

That is 65 years across ~70 markets, versus 26.8 years across 9 pairs for the
FX panel in Exp10. It also happens to match the natural rebalancing frequency
of classic time-series momentum (Moskowitz-Ooi-Pedersen 2012 rebalance
monthly), so the monthly sampling is a feature here, not a compromise.

CAVEATS THAT MATTER FOR INTERPRETATION
--------------------------------------
1. These are monthly AVERAGE prices, not month-end closes. A signal formed
   from month t's average is only fully known once month t has ended, so
   entry must be at t+1 (the first trading day of month t+1). We obey that.
2. The Pink Sheet is published with a lag (typically the following month),
   so a live strategy would face a further delay. This study measures the
   signal, not the operational latency.
3. Some series start late or have gaps; we keep only columns with enough
   history and report what was dropped.
4. Prices are spot/average, NOT futures, so this ignores roll yield. For
   commodities in contango that is a material drag and the result here is
   therefore an upper bound on an implementable futures strategy.

USAGE
    python3 scripts/worldbank/fetch_commodities.py
    python3 scripts/worldbank/fetch_commodities.py --force
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# The Pink Sheet workbook URL rotates; these are tried in order.
URLS = [
    "https://thedocs.worldbank.org/en/doc/18675f1d1639c7a34d463f59263ba0a2"
    "-0050012025/related/CMO-Historical-Data-Monthly.xlsx",
    "https://thedocs.worldbank.org/en/doc/5d903e848db1d1b83e0ec8f744e55570"
    "-0350012021/related/CMO-Historical-Data-Monthly.xlsx",
]

OUT_DIR = Path("data/real/worldbank_commodities")

# Columns that are indices, aggregates or duplicates rather than tradable prices.
DROP_PATTERNS = (
    "index",
    "average",
    "avg",
    "total",
    "weight",
)


def fetch(dest: Path) -> Path:
    """Download the Pink Sheet workbook, skipping if already present."""
    if dest.exists() and dest.stat().st_size > 100_000:
        print(f"  cached: {dest} ({dest.stat().st_size/1024:.0f} KB)")
        return dest
    import urllib.request

    last_err: Exception | None = None
    for url in URLS:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
                f.write(r.read())
            print(f"  downloaded {dest.stat().st_size/1024:.0f} KB")
            return dest
        except Exception as e:  # noqa: BLE001
            last_err = e
            print(f"  failed: {url[:60]}... ({e})")
    raise RuntimeError(f"all Pink Sheet URLs failed: {last_err}")


def parse_monthly_prices(xlsx: Path) -> pd.DataFrame:
    """Read the 'Monthly Prices' sheet, auto-locating the header row."""
    xl = pd.ExcelFile(xlsx)
    if "Monthly Prices" not in xl.sheet_names:
        raise RuntimeError(f"sheets={xl.sheet_names}")

    best = None
    for hr in range(0, 12):
        d = xl.parse("Monthly Prices", header=hr)
        named = [c for c in d.columns
                 if any(ch.isalpha() for ch in str(c)) and not str(c).startswith("Unnamed")]
        if len(named) >= 20:
            best = (hr, d, len(named))
            break
    if best is None:
        raise RuntimeError("could not locate header row")

    hr, d, ncol = best
    print(f"  header row = {hr}, {ncol} named columns")

    # The first column holds the period label like '1960M01'.
    first = d.columns[0]
    per = d[first].astype(str)
    mask = per.str.match(r"^\d{4}M\d{2}$", na=False)
    d = d.loc[mask].copy()
    if d.empty:
        raise RuntimeError("no period labels like '1960M01' found")

    # Labels look like '1960M01', which PeriodIndex cannot parse directly.
    labels = per[mask].astype(str).to_numpy()
    idx = pd.PeriodIndex([f"{s[:4]}-{s[5:7]}" for s in labels], freq="M")
    out = pd.DataFrame(index=idx)
    for c in d.columns[1:]:
        s = pd.to_numeric(d[c], errors="coerce")
        out[str(c).strip()] = s.to_numpy()
    out.index.name = "month"
    return out


def clean(df: pd.DataFrame, min_obs: int = 240) -> tuple[pd.DataFrame, dict]:
    """Drop index/aggregate columns and thin series; report what was removed."""
    dropped: dict[str, str] = {}

    keep_cols = []
    for c in df.columns:
        lc = c.lower()
        if any(p in lc for p in DROP_PATTERNS):
            dropped[c] = "index/aggregate column"
            continue
        if df[c].notna().sum() < min_obs:
            dropped[c] = f"only {df[c].notna().sum()} observations"
            continue
        keep_cols.append(c)
    out = df[keep_cols].copy()

    # Prices must be positive to take logs.
    bad = [c for c in out.columns if (out[c] <= 0).any()]
    for c in bad:
        dropped[c] = "non-positive price"
    out = out.drop(columns=bad)

    out = out.sort_index()
    return out, dropped


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true", help="re-download even if cached")
    ap.add_argument("--min-obs", type=int, default=240)
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    xlsx = OUT_DIR / "CMO-Historical-Data-Monthly.xlsx"
    if args.force and xlsx.exists():
        xlsx.unlink()

    print("Fetching World Bank Pink Sheet...")
    try:
        fetch(xlsx)
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    print("Parsing...")
    raw = parse_monthly_prices(xlsx)
    print(f"  raw: {raw.shape[0]} months x {raw.shape[1]} series "
          f"({raw.index[0]} .. {raw.index[-1]})")

    px, dropped = clean(raw, min_obs=args.min_obs)
    print(f"  clean: {px.shape[0]} months x {px.shape[1]} series")
    if dropped:
        print(f"  dropped {len(dropped)} columns:")
        for k, v in list(dropped.items())[:12]:
            print(f"    - {k[:52]}: {v}")
        if len(dropped) > 12:
            print(f"    ... and {len(dropped)-12} more")

    out = OUT_DIR / "commodities_monthly.csv"
    px.to_csv(out)
    print(f"\nWrote {out}  ({out.stat().st_size/1024:.0f} KB)")
    print(f"  span: {px.index[0]} .. {px.index[-1]}  ({len(px)} months)")
    print(f"  series: {len(px.columns)}")
    print("\nFirst 8 series:")
    for c in px.columns[:8]:
        s = px[c].dropna()
        print(f"  {c[:44]:<44} n={len(s):>4}  {s.index[0]}..{s.index[-1]}  "
              f"last={s.iloc[-1]:.2f}")
    print("\nCoverage of the recent window (last 12 months non-null per series):")
    recent = px.iloc[-12:].notna().sum()
    print(f"  series with all 12: {(recent == 12).sum()} / {len(px.columns)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
