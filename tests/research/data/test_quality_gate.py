"""Tests for the research data Quality Gate."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from research.data.bar import Bar
from research.data.quality_gate import run_quality_gate
from research.data.types import TimeFrame
from research.universe.research_universe import by_symbol


def _bar(ts: datetime, close: float = 100.0) -> Bar:
    return Bar(
        symbol="SPY",
        timestamp=ts,
        open=close,
        high=close + 0.5,
        low=close - 0.5,
        close=close,
        volume=1_000_000,
    )


def _three_year_daily_bars() -> list[Bar]:
    """Weekday daily bars spanning 2023..2025 (three calendar years)."""
    bars: list[Bar] = []
    d = datetime(2023, 1, 2)
    end = datetime(2025, 12, 31)
    while d <= end:
        if d.weekday() < 5:
            bars.append(_bar(d))
        d += timedelta(days=1)
    return bars


@pytest.fixture(scope="module")
def spy() -> object:
    return by_symbol("SPY")


def test_valid_series_passes(spy):
    report = run_quality_gate(_three_year_daily_bars(), spy, TimeFrame.D1)
    assert report.status == "PASS"
    assert report.passed_checks == len(report.checks)


def test_empty_series_fails(spy):
    report = run_quality_gate([], spy, TimeFrame.D1)
    assert report.status == "FAIL"
    by_name = {c.name: c.passed for c in report.checks}
    assert by_name["bars_non_empty"] is False


def test_insufficient_coverage_fails(spy):
    bars = [_bar(datetime(2024, 1, 2) + timedelta(days=i)) for i in range(250)]
    report = run_quality_gate(bars, spy, TimeFrame.D1)
    assert report.status == "FAIL"
    by_name = {c.name: c.passed for c in report.checks}
    assert by_name["coverage_years"] is False


def test_duplicate_timestamps_fail(spy):
    bars = _three_year_daily_bars()
    bars.insert(50, _bar(bars[50].timestamp))  # duplicate timestamp
    report = run_quality_gate(bars, spy, TimeFrame.D1)
    assert report.status == "FAIL"
    by_name = {c.name: c.passed for c in report.checks}
    assert by_name["no_duplicate_timestamps"] is False


def test_out_of_order_fails(spy):
    bars = _three_year_daily_bars()
    bars[10], bars[11] = bars[11], bars[10]
    report = run_quality_gate(bars, spy, TimeFrame.D1)
    assert report.status == "FAIL"
    by_name = {c.name: c.passed for c in report.checks}
    assert by_name["monotonic_timestamps"] is False


def test_bad_ohlc_fails(spy):
    bars = _three_year_daily_bars()
    bars[5] = Bar(
        symbol="SPY", timestamp=bars[5].timestamp,
        open=100.0, high=90.0, low=95.0, close=100.0, volume=1,
    )
    report = run_quality_gate(bars, spy, TimeFrame.D1)
    assert report.status == "FAIL"
    by_name = {c.name: c.passed for c in report.checks}
    assert by_name["ohlc_consistency"] is False


def test_missing_fields_fail(spy):
    bars = _three_year_daily_bars()
    bars[5] = Bar(
        symbol="SPY", timestamp=bars[5].timestamp,
        open=100.0, high=None, low=95.0, close=100.0, volume=1,
    )
    report = run_quality_gate(bars, spy, TimeFrame.D1)
    assert report.status == "FAIL"
    by_name = {c.name: c.passed for c in report.checks}
    assert by_name["no_missing_fields"] is False


def test_bad_cadence_fails():
    # 15m series with one 7-minute gap -> not a multiple of 15m
    base = datetime(2023, 1, 2, 9, 30)
    bars = [Bar(symbol="SPY", timestamp=base + timedelta(minutes=15 * i),
                open=100, high=101, low=99, close=100, volume=1)
            for i in range(10)]
    # corrupt gap: 9:45 -> 9:52 (7 minutes)
    bars[1] = Bar(symbol="SPY", timestamp=base + timedelta(minutes=7),
                  open=100, high=101, low=99, close=100, volume=1)
    report = run_quality_gate(bars, by_symbol("SPY"), TimeFrame.M15)
    assert report.status == "FAIL"
    by_name = {c.name: c.passed for c in report.checks}
    assert by_name["cadence"] is False


def test_continuous_contract_metadata(spy):
    report = run_quality_gate(_three_year_daily_bars(), spy, TimeFrame.D1)
    assert report.detail["session"]  # session info present
