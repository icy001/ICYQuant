"""Generate deterministic NVDA 15m OHLCV data for Strategy 001 backtesting.

Writes `data/lakehouse/NVDA_15m.csv` consumable by
`research.data.csv_provider.CsvMarketDataProvider` (columns:
timestamp, open, high, low, close, volume).

The series is a seeded geometric-Brownian walk with alternating drift
segments, producing a handful of moving-average crosses so the dual-MA
Strategy 001 generates meaningful trades. Fully reproducible (fixed seed).

Usage:
    python infra/scripts/generate_nvda_15m.py [--output PATH] [--seed N]
"""
from __future__ import annotations

import argparse
import math
import random
from datetime import date, datetime, time, timedelta
from pathlib import Path

DEFAULT_OUTPUT = Path(__file__).resolve().parents[2] / "data" / "lakehouse" / "NVDA_15m.csv"

START_DATE = date(2025, 4, 1)
END_DATE = date(2025, 7, 1)          # exclusive
SESSION_OPEN = time(9, 30)
SESSION_CLOSE = time(16, 0)
BAR_MINUTES = 15
BARS_PER_DAY = 26                    # 09:30 -> 15:45, 15-minute bars

START_PRICE = 120.0
BAR_VOL = 0.0016                     # per-bar (15m) volatility
BASE_VOLUME = 3_000_000

# (duration_days, drift_per_bar) - alternating trend segments.
# Segment durations (4-8 days) are chosen so the long MA (60 bars ~ 2.3
# days) is crossed several times, giving the dual-MA strategy a handful
# of trades over the 3-month window.
DRIFT_SEGMENTS = [
    (7, 0.0011),   # up
    (4, -0.0012),  # sharp down
    (6, 0.0014),   # strong up
    (5, -0.0009),  # down
    (8, 0.0008),   # up
    (4, -0.0013),  # sharp down
    (7, 0.0010),   # recovery up
]


def _trade_days(start: date, end: date) -> list[date]:
    days: list[date] = []
    d = start
    while d < end:
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)
    return days


def generate(seed: int) -> list[dict]:
    rng = random.Random(seed)
    bars: list[dict] = []

    drift_idx = 0
    seg_remaining = DRIFT_SEGMENTS[0][0]
    drift = DRIFT_SEGMENTS[0][1]

    prev_close = START_PRICE

    for day in _trade_days(START_DATE, END_DATE):
        for slot in range(BARS_PER_DAY):
            minutes = 9 * 60 + 30 + slot * BAR_MINUTES
            ts = datetime.combine(day, time(minutes // 60, minutes % 60))

            seg_remaining -= 1
            if seg_remaining <= 0:
                drift_idx = (drift_idx + 1) % len(DRIFT_SEGMENTS)
                seg_remaining = DRIFT_SEGMENTS[drift_idx][0]
                drift = DRIFT_SEGMENTS[drift_idx][1]

            z = rng.gauss(0.0, 1.0)
            open_price = prev_close
            close = open_price * math.exp(drift + BAR_VOL * z)
            spread = abs(z) * 0.25 * BAR_VOL * close
            high = max(open_price, close) + spread
            low = min(open_price, close) - spread
            volume = int(BASE_VOLUME * (0.6 + 0.8 * rng.random()))

            bars.append(
                {
                    "timestamp": ts.isoformat(),
                    "open": round(open_price, 2),
                    "high": round(high, 2),
                    "low": round(low, 2),
                    "close": round(close, 2),
                    "volume": volume,
                }
            )
            prev_close = close

    return bars


def write_csv(bars: list[dict], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as fp:
        fp.write("timestamp,open,high,low,close,volume\n")
        for b in bars:
            fp.write(
                f"{b['timestamp']},{b['open']},{b['high']},{b['low']},"
                f"{b['close']},{b['volume']}\n"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    bars = generate(args.seed)
    write_csv(bars, args.output)
    first, last = bars[0]["timestamp"], bars[-1]["timestamp"]
    closes = [b["close"] for b in bars]
    print(f"generated {len(bars)} bars ({first} -> {last})")
    print(f"price range: {min(closes):.2f} - {max(closes):.2f}")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
