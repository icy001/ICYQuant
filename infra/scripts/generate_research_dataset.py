"""Generate the Research Universe v1.1 synthetic dataset (nine assets).

Produces, for every asset in ``RESEARCH_UNIVERSE_V1_1``, a deterministic
seeded GBM series covering >= ``--years`` (default 3) years at 15m / 1h / 1d.

Timestamps are *naive local* in the asset's timezone and follow the asset's
trading session (US / CN / HK / 24h FX & gold / SHFE with night session).
Output layout (mirrors Raw -> Processed -> Manifest -> Quality Gate):

    data/processed/{symbol}_{timeframe}.csv      — clean series (quality gated)
    data/manifests/{symbol}_{timeframe}.json     — DatasetManifest + gate result

The existing 3-month ``data/lakehouse/NVDA_15m.csv`` (Strategy 001 fixture)
is left untouched.

Usage:
    python infra/scripts/generate_research_dataset.py [--assets ...] [--timeframes ...]
                                                     [--years 3] [--seed 7]
"""
from __future__ import annotations

import argparse
import math
import random
from datetime import date, datetime, time, timedelta
from pathlib import Path

from research.data.csv_provider import CsvMarketDataProvider
from research.data.manifest import DatasetManifest, QualityGateResult, write_manifest
from research.data.quality_gate import run_quality_gate
from research.data.types import TimeFrame
from research.universe.research_universe import RESEARCH_UNIVERSE_V1_1, by_symbol

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROCESSED = PROJECT_ROOT / "data" / "processed"
DEFAULT_RAW = PROJECT_ROOT / "data" / "raw"

DEFAULT_YEARS = 3
DEFAULT_SEED = 7

# (duration_days, drift_per_bar_15m) — alternating trend segments, cycled.
DRIFT_SEGMENTS = [
    (30, 0.0006),
    (15, -0.0009),
    (25, 0.0010),
    (12, -0.0011),
    (20, 0.0005),
    (10, -0.0013),
]

# Per-asset GBM tuning: start price, per-15m-bar volatility, base volume.
ASSET_TUNING = {
    "NVDA": dict(start=150.0, vol15=0.0030, base_volume=3_000_000),
    "SPY": dict(start=400.0, vol15=0.0016, base_volume=80_000_000),
    "QQQ": dict(start=280.0, vol15=0.0020, base_volume=40_000_000),
    "000688.SH": dict(start=950.0, vol15=0.0025, base_volume=20_000_000),
    "HSTECH": dict(start=3500.0, vol15=0.0030, base_volume=30_000_000),
    "EURUSD": dict(start=1.08, vol15=0.0005, base_volume=100_000),
    "XAUUSD": dict(start=1800.0, vol15=0.0012, base_volume=50_000),
    "AU": dict(start=400.0, vol15=0.0012, base_volume=500_000),
    "AG": dict(start=5000.0, vol15=0.0022, base_volume=1_000_000),
}

# --- per-schedule day slots -------------------------------------------------
# Each entry: (slots_15m, slots_1h, opener) where opener builds the day's
# first bar time; slots are spaced by the timeframe. SHFE has a rollover
# night session (21:00 -> 02:30 next day) appended after the day session.

_US_OPEN = time(9, 30)        # 26 x 15m / 7 x 1h
_CN_OPEN = time(9, 30)        # 8 + 8 x 15m (11:30 break) / 4 x 1h
_HK_OPEN = time(9, 30)        # 10 + 12 x 15m (12:00 break) / 6 x 1h
_FX_OPEN = time(0, 0)         # 96 x 15m / 24 x 1h
_SHFE_OPEN = time(9, 0)       # 10 + 6 x 15m (11:30 break) / 6 x 1h
_SHFE_NIGHT_OPEN = time(21, 0)  # +22 x 15m / +6 x 1h (rollover)


def _day_slots(schedule: str, bar_minutes: int) -> list[time]:
    """Return the intraday bar start times for one trading day.

    All returned gaps are whole multiples of ``bar_minutes`` so the
    quality-gate cadence check passes (lunch breaks / overnight gaps are
    multiples of the bar length). SHFE night bars (21:00 -> 02:30) roll over
    midnight; the caller bumps the date when a slot goes backwards.
    """
    def times_from(start: time, n: int, minutes: int) -> list[time]:
        base = start.hour * 60 + start.minute
        return [time((base + i * minutes) // 60 % 24, (base + i * minutes) % 60)
                for i in range(n)]

    if bar_minutes == 1440:
        return [time(0, 0)]
    step = bar_minutes
    if schedule == "US":
        return times_from(_US_OPEN, 26 if step == 15 else 7, step)
    if schedule == "CN":
        if step == 15:
            return times_from(_CN_OPEN, 8, 15) + times_from(time(13, 0), 8, 15)
        # 09:30,10:30,11:30 + 13:30,14:30 (11:30->13:30 = 120m = 2 bars)
        return times_from(_CN_OPEN, 3, 60) + times_from(time(13, 30), 2, 60)
    if schedule == "HK":
        if step == 15:
            return times_from(_HK_OPEN, 10, 15) + times_from(time(13, 0), 12, 15)
        return times_from(_HK_OPEN, 3, 60) + times_from(time(13, 30), 3, 60)
    if schedule == "FX":
        return times_from(_FX_OPEN, 96 if step == 15 else 24, step)
    if schedule == "SHFE":
        if step == 15:
            day = times_from(_SHFE_OPEN, 10, 15) + times_from(time(13, 30), 6, 15)
        else:
            day = times_from(_SHFE_OPEN, 7, 60)  # 09:00..15:00 hourly
        night = times_from(_SHFE_NIGHT_OPEN, 22 if step == 15 else 6, step)
        return day + night
    raise ValueError(f"Unknown schedule: {schedule}")


def _trade_days(start: date, end: date) -> list[date]:
    """Weekday trading calendar (holidays intentionally ignored for synthetic)."""
    days: list[date] = []
    d = start
    while d < end:
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)
    return days


def _generate_asset(symbol: str, timeframe: TimeFrame, years: int,
                    seed: int) -> list[dict]:
    asset = by_symbol(symbol)
    tuning = ASSET_TUNING[symbol]
    if asset.exchange == "SHFE":
        schedule = "SHFE"  # day + rollover night session
    else:
        schedule = {"US": "US", "CN": "CN", "HK": "HK"}.get(asset.region, "FX")
    bar_minutes = {
        TimeFrame.M15: 15,
        TimeFrame.H1: 60,
        TimeFrame.D1: 1440,
    }[timeframe]
    bars_per_day = len(_day_slots(schedule, bar_minutes))

    # scale per-bar vol from the 15m reference
    ref_bpd = len(_day_slots(schedule, 15))
    vol = tuning["vol15"] * math.sqrt(ref_bpd / bars_per_day) if bars_per_day else 0.0

    rng = random.Random(f"{symbol}:{timeframe.value}:{seed}")
    end_year = 2023 + years - 1
    days = _trade_days(date(2023, 1, 1), date(end_year + 1, 1, 1))

    drift_idx, seg_remaining = 0, DRIFT_SEGMENTS[0][0]
    drift = DRIFT_SEGMENTS[0][1]
    prev_close = tuning["start"]
    bars: list[dict] = []
    prev_ts: datetime | None = None

    for base_day in days:
        day = base_day
        for tod in _day_slots(schedule, bar_minutes):
            ts = datetime.combine(day, tod)
            # rollover session: slot went back in time -> next calendar day
            if prev_ts is not None and ts <= prev_ts:
                day = day + timedelta(days=1)
                ts = datetime.combine(day, tod)
            prev_ts = ts

            seg_remaining -= 1
            if seg_remaining <= 0:
                drift_idx = (drift_idx + 1) % len(DRIFT_SEGMENTS)
                seg_remaining = DRIFT_SEGMENTS[drift_idx][0]
                drift = DRIFT_SEGMENTS[drift_idx][1]

            z = rng.gauss(0.0, 1.0)
            open_price = prev_close
            close = open_price * math.exp(drift + vol * z)
            spread = abs(z) * 0.25 * vol * close
            high = max(open_price, close) + spread
            low = min(open_price, close) - spread
            volume = int(tuning["base_volume"] * (0.6 + 0.8 * rng.random()))

            decimals = 4 if (asset.currency == "USD" and asset.asset_class == "fx") else 2
            bars.append({
                "timestamp": ts.isoformat(),
                "open": round(open_price, decimals),
                "high": round(high, decimals),
                "low": round(low, decimals),
                "close": round(close, decimals),
                "volume": volume,
            })
            prev_close = close

    return bars


def _write_csv(bars: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fp:
        fp.write("timestamp,open,high,low,close,volume\n")
        for b in bars:
            fp.write(f"{b['timestamp']},{b['open']},{b['high']},{b['low']},"
                     f"{b['close']},{b['volume']}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", default=",".join(
        a.symbol for a in RESEARCH_UNIVERSE_V1_1))
    parser.add_argument("--timeframes", default="15m,1h,1d")
    parser.add_argument("--years", type=int, default=DEFAULT_YEARS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--processed-root", type=Path, default=DEFAULT_PROCESSED)
    parser.add_argument("--no-validate", action="store_true",
                        help="generate CSV only; skip quality gate + manifest")
    args = parser.parse_args()

    assets = [a for a in RESEARCH_UNIVERSE_V1_1 if a.symbol in args.assets.split(",")]
    timeframes = [TimeFrame(tf) for tf in args.timeframes.split(",")]

    provider = CsvMarketDataProvider(args.processed_root)
    summary: list[dict] = []
    failed = 0

    for asset in assets:
        for tf in timeframes:
            bars = _generate_asset(asset.symbol, tf, args.years, args.seed)
            csv_path = args.processed_root / f"{asset.symbol}_{tf.value}.csv"
            _write_csv(bars, csv_path)

            if args.no_validate:
                print(f"generated {csv_path} ({len(bars)} bars)")
                continue

            loaded = provider.load_bars(asset.symbol, tf)
            report = run_quality_gate(loaded, asset, tf, min_years=args.years)
            base = DatasetManifest.build(asset, tf, loaded, min_years=args.years)
            manifest = DatasetManifest(
                symbol=base.symbol, timeframe=base.timeframe,
                source=base.source, timezone=base.timezone,
                session=base.session, continuous_contract=base.continuous_contract,
                start=base.start, end=base.end, bars=base.bars,
                min_years=base.min_years,
                quality_gate=QualityGateResult(
                    status=report.status,
                    checks={c.name: c.passed for c in report.checks},
                    detail=report.detail,
                    run_at=datetime.now().isoformat(timespec="seconds"),
                ),
                generated_at=base.generated_at,
            )
            write_manifest(manifest, args.processed_root)

            ok = report.status == "PASS"
            failed += 0 if ok else 1
            summary.append({
                "symbol": asset.symbol, "tf": tf.value, "bars": len(loaded),
                "status": report.status, "checks": report.passed_checks,
                "span_years": round(report.detail.get("span_years", 0.0), 2),
            })
            mark = "PASS" if ok else "FAIL"
            print(f"[{mark}] {asset.symbol:10s} {tf.value:4s} "
                  f"{len(loaded):7d} bars  {report.passed_checks}/"
                  f"{len(report.checks)} checks  "
                  f"{report.detail.get('span_years', 0.0):.2f}y")

    if summary and not args.no_validate:
        n_pass = sum(1 for s in summary if s["status"] == "PASS")
        print(f"\nquality gate: {n_pass}/{len(summary)} datasets PASS, "
              f"{failed} FAIL")
        print(f"manifests -> {args.processed_root / 'manifests'}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
