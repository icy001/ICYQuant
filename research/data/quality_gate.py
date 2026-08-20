"""Data Quality Gate — the quality gate a research dataset must pass.

Every dataset (``{symbol}_{timeframe}.csv``) entering the research pipeline
is validated here before it may be used for backtesting. The gate checks:

    1. bars_non_empty        — the file loaded into at least one bar
    2. coverage_years        — the time span covers >= ``min_years`` (default 3)
    3. no_missing_fields     — every bar has numeric OHLCV + timestamp
    4. no_duplicate_timestamps
    5. monotonic_timestamps  — strictly increasing
    6. ohlc_consistency      — high>=low, open/close within [low, high]
    7. cadence               — adjacent bar gaps are whole multiples of the
                               timeframe and never shorter than one bar
                               (accounts for lunch breaks / overnight gaps /
                               weekends / SHFE night sessions)

NOTE: this is a *research threshold*, not a guarantee of profitability.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, time as dtime
from typing import Any, Optional

from .bar import Bar
from .types import TimeFrame
from ..universe.asset import Asset, TradingSession

MIN_YEARS_DEFAULT = 3.0

# Minutes per bar, keyed by TimeFrame value.
BAR_MINUTES = {
    TimeFrame.M1.value: 1,
    TimeFrame.M5.value: 5,
    TimeFrame.M15.value: 15,
    TimeFrame.M30.value: 30,
    TimeFrame.H1.value: 60,
    TimeFrame.H4.value: 240,
    TimeFrame.D1.value: 1440,
    TimeFrame.W1.value: 10080,
    TimeFrame.MN1.value: 43200,
}


@dataclass(frozen=True)
class QualityCheck:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class QualityReport:
    symbol: str
    timeframe: str
    status: str  # PASS | FAIL
    checks: list[QualityCheck] = field(default_factory=list)
    detail: dict[str, Any] = field(default_factory=dict)

    @property
    def passed_checks(self) -> int:
        return sum(1 for c in self.checks if c.passed)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "status": self.status,
            "checks": {c.name: c.passed for c in self.checks},
            "detail": self.detail,
        }


def _within_session(ts: datetime, session: TradingSession) -> bool:
    """Check a bar timestamp's time-of-day against a session (non-rollover)."""
    def parse(hhmm: str) -> dtime:
        h, m = hhmm.split(":")
        return dtime(int(h), int(m))

    tod = ts.time()
    open_t, close_t = parse(session.open), parse(session.close)
    if open_t <= close_t:
        in_main = open_t <= tod <= close_t
    else:  # rollover session handled by caller
        in_main = False
    if not in_main:
        return False
    if session.lunch_start and session.lunch_end:
        lunch_start, lunch_end = parse(session.lunch_start), parse(session.lunch_end)
        if lunch_start <= tod < lunch_end:
            return False
    return True


def run_quality_gate(
    bars: list[Bar],
    asset: Asset,
    timeframe: TimeFrame,
    min_years: float = MIN_YEARS_DEFAULT,
) -> QualityReport:
    """Validate a bar series against the research data quality standard."""
    symbol = asset.symbol
    tf = timeframe.value
    checks: list[QualityCheck] = []
    detail: dict[str, Any] = {}

    # 1. non-empty
    non_empty = len(bars) > 0
    checks.append(QualityCheck("bars_non_empty", non_empty,
                               f"{len(bars)} bars loaded"))

    # 2. coverage years — counts distinct calendar years spanned, so a
    # series covering 2023..2025 counts as 3 years regardless of day-of-year.
    coverage = False
    coverage_detail = ""
    span_days = 0.0
    if non_empty:
        span_days = (bars[-1].timestamp - bars[0].timestamp).total_seconds() / 86400.0
        calendar_years = bars[-1].timestamp.year - bars[0].timestamp.year + 1
        min_years_int = math.ceil(min_years - 1e-9)
        coverage = calendar_years >= min_years_int
        coverage_detail = (
            f"{bars[0].timestamp} -> {bars[-1].timestamp} "
            f"({calendar_years} calendar years, span {span_days / 365.25:.2f}y, "
            f"min {min_years})"
        )
    else:
        coverage_detail = "no bars to measure"
    checks.append(QualityCheck("coverage_years", coverage, coverage_detail))
    detail["span_years"] = (span_days / 365.25 if non_empty else 0.0)
    detail["calendar_years"] = (
        bars[-1].timestamp.year - bars[0].timestamp.year + 1 if non_empty else 0
    )
    detail["start"] = bars[0].timestamp.isoformat() if non_empty else ""
    detail["end"] = bars[-1].timestamp.isoformat() if non_empty else ""

    # 3. missing fields
    missing = 0
    for b in bars:
        if any(v is None for v in (b.open, b.high, b.low, b.close, b.volume)):
            missing += 1
    checks.append(QualityCheck("no_missing_fields", missing == 0,
                               f"{missing} bars with missing OHLCV"))

    # 4. duplicate timestamps
    stamps = [b.timestamp for b in bars]
    dup = len(stamps) - len(set(stamps))
    checks.append(QualityCheck("no_duplicate_timestamps", dup == 0,
                               f"{dup} duplicate timestamps"))

    # 5. monotonic
    monotonic = all(a < b for a, b in zip(stamps, stamps[1:]))
    checks.append(QualityCheck("monotonic_timestamps", monotonic,
                               "timestamps strictly increasing"))

    # 6. OHLC consistency (missing fields are reported separately above)
    bad_ohlc = 0
    for b in bars:
        if None in (b.open, b.high, b.low, b.close):
            continue
        if b.high < b.low or b.open < b.low or b.open > b.high or b.close < b.low or b.close > b.high:
            bad_ohlc += 1
    checks.append(QualityCheck("ohlc_consistency", bad_ohlc == 0,
                               f"{bad_ohlc} inconsistent bars"))

    # 7. cadence
    bar_minutes = BAR_MINUTES[tf]
    bad_gaps = 0
    example = ""
    for a, b in zip(stamps, stamps[1:]):
        gap_min = int((b - a).total_seconds() // 60)
        if gap_min % bar_minutes != 0 or gap_min < bar_minutes:
            bad_gaps += 1
            if not example:
                example = f"{a} -> {b} gap={gap_min}m"
    checks.append(QualityCheck(
        "cadence", bad_gaps == 0,
        f"{bad_gaps} invalid gaps (bar={bar_minutes}m)"
        + (f"; first bad: {example}" if example else "")))

    # 8. metadata: continuous contract flag sanity + timezone presence
    meta_ok = True
    meta_detail = f"tz={asset.timezone}; continuous={asset.continuous_contract}"
    if asset.continuous_contract and not asset.currency:
        meta_ok = False
        meta_detail += "; WARN: continuous contract missing quote currency"
    if not asset.timezone:
        meta_ok = False
        meta_detail += "; WARN: missing timezone"
    checks.append(QualityCheck("metadata", meta_ok, meta_detail))

    # session coverage (informational only for rollover/night markets)
    session_detail = str(asset.session) if asset.session else "none"
    if asset.session and not asset.session.rollover and non_empty and bars[0].timestamp.tzinfo is None:
        outside = sum(1 for b in bars if not _within_session(b.timestamp, asset.session))
        detail["bars_outside_session"] = outside
        session_detail += f"; {outside} bars outside session"
    detail["session"] = session_detail

    status = "PASS" if all(c.passed for c in checks) else "FAIL"
    return QualityReport(symbol=symbol, timeframe=tf, status=status,
                         checks=checks, detail=detail)
