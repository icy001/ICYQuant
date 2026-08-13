"""
Tests for AlertFingerprint / AlertDeduplicator / AlertStormProtector
(Commit 27 Part 1.3, spec sections 13-15, 23, 32-33).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from services.operations import (
    AlertDeduplicator,
    AlertFingerprint,
    AlertStormProtector,
)


class _FakeClock:
    def __init__(self) -> None:
        self._now = datetime(2026, 8, 13, 0, 0, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += timedelta(seconds=seconds)


def test_duplicate_alert_is_suppressed():
    """spec section 32: register 后 is_duplicate 为 True。"""
    dedup = AlertDeduplicator()

    fingerprint = "abc"

    assert not dedup.is_duplicate(fingerprint)

    dedup.register(fingerprint)

    assert dedup.is_duplicate(fingerprint)


def test_alert_resolves():
    """spec section 33: resolve 后 is_duplicate 为 False。"""
    dedup = AlertDeduplicator()

    fingerprint = "abc"

    dedup.register(fingerprint)

    dedup.resolve(fingerprint)

    assert not dedup.is_duplicate(fingerprint)


def test_fingerprint_is_stable():
    """spec section 14: 相同输入永远得到相同 fingerprint。"""
    first = AlertFingerprint.build(
        "execution-latency-high",
        "execution-01",
        {"venue": "NASDAQ"},
    )

    second = AlertFingerprint.build(
        "execution-latency-high",
        "execution-01",
        {"venue": "NASDAQ"},
    )

    assert first == second


def test_fingerprint_differs_by_rule():
    fp_a = AlertFingerprint.build(
        "rule-a",
        "execution-01",
        {},
    )

    fp_b = AlertFingerprint.build(
        "rule-b",
        "execution-01",
        {},
    )

    assert fp_a != fp_b


def test_fingerprint_differs_by_service():
    fp_a = AlertFingerprint.build(
        "execution-latency-high",
        "execution-01",
        {},
    )

    fp_b = AlertFingerprint.build(
        "execution-latency-high",
        "execution-02",
        {},
    )

    assert fp_a != fp_b


def test_fingerprint_differs_by_labels():
    fp_a = AlertFingerprint.build(
        "venue-latency-high",
        None,
        {"venue": "NASDAQ"},
    )

    fp_b = AlertFingerprint.build(
        "venue-latency-high",
        None,
        {"venue": "NYSE"},
    )

    assert fp_a != fp_b


def test_storm_protector_detects_storm():
    """spec section 23: 窗口内超过 max 则 Storm Detected。"""
    clock = _FakeClock()
    protector = AlertStormProtector(
        max_alerts_per_window=3,
        window_seconds=60.0,
        clock=clock,
    )

    assert not protector.record()
    assert not protector.record()
    assert not protector.record()

    assert protector.record() is True

    assert protector.storm_detected
    assert protector.suppression_mode


def test_storm_protector_expires_window():
    """超过窗口时间后，旧的 firing 不再计入窗口。"""
    clock = _FakeClock()
    protector = AlertStormProtector(
        max_alerts_per_window=3,
        window_seconds=60.0,
        clock=clock,
    )

    protector.record()
    protector.record()
    protector.record()

    clock.advance(61)

    assert not protector.record()


def test_storm_protector_release():
    clock = _FakeClock()
    protector = AlertStormProtector(
        max_alerts_per_window=1,
        window_seconds=60.0,
        clock=clock,
    )

    protector.record()
    protector.record()

    assert protector.suppression_mode

    protector.release()

    assert not protector.suppression_mode
    assert not protector.storm_detected
