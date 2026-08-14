"""Tests for the strategy runtime heartbeat protocol."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

import pytest

from services.strategy.runtime.heartbeat import (
    DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
    DEFAULT_HEARTBEAT_TIMEOUT_SECONDS,
    HeartbeatTracker,
    RuntimeHeartbeat,
    utcnow,
)
from services.strategy.runtime.state import RuntimeState


def make_heartbeat(
    strategy_id: str = "STRAT-001",
    state: str = "RUNNING",
    now: datetime | None = None,
    sequence: int = 1,
) -> RuntimeHeartbeat:
    return RuntimeHeartbeat(
        strategy_id=strategy_id,
        runtime_id="RUNTIME-001",
        timestamp=now if now is not None else utcnow(),
        sequence=sequence,
        state=state,
    )


class TestRuntimeHeartbeat:
    def test_heartbeat_carries_expected_fields(self) -> None:
        now = utcnow()
        heartbeat = make_heartbeat(now=now, sequence=7)

        assert heartbeat.strategy_id == "STRAT-001"
        assert heartbeat.runtime_id == "RUNTIME-001"
        assert heartbeat.timestamp == now
        assert heartbeat.sequence == 7
        assert heartbeat.state == "RUNNING"

    def test_heartbeat_is_immutable(self) -> None:
        heartbeat = make_heartbeat()
        with pytest.raises(FrozenInstanceError):
            heartbeat.sequence = 99  # type: ignore[misc]

    def test_default_interval_and_timeout(self) -> None:
        assert DEFAULT_HEARTBEAT_INTERVAL_SECONDS == 5.0
        assert DEFAULT_HEARTBEAT_TIMEOUT_SECONDS == 30.0


class TestHeartbeatTracker:
    def test_no_heartbeat_reports_unknown(self) -> None:
        tracker = HeartbeatTracker()
        assert tracker.state("STRAT-001") == RuntimeState.UNKNOWN.value
        assert tracker.is_stale("STRAT-001")

    def test_record_updates_last_heartbeat(self) -> None:
        tracker = HeartbeatTracker()
        heartbeat = make_heartbeat(state="READY")
        tracker.record(heartbeat)

        assert tracker.last("STRAT-001") is heartbeat
        assert not tracker.is_stale("STRAT-001")
        assert tracker.state("STRAT-001") == "READY"

    def test_stale_heartbeat_reports_unknown(self) -> None:
        tracker = HeartbeatTracker(timeout_seconds=30.0)
        old = utcnow() - timedelta(seconds=60)
        tracker.record(make_heartbeat(now=old))

        assert tracker.is_stale("STRAT-001")
        assert tracker.state("STRAT-001") == RuntimeState.UNKNOWN.value

    def test_fresh_heartbeat_is_not_stale(self) -> None:
        tracker = HeartbeatTracker(timeout_seconds=30.0)
        tracker.record(make_heartbeat(now=utcnow()))

        assert not tracker.is_stale("STRAT-001")

    def test_expire_forces_unknown(self) -> None:
        tracker = HeartbeatTracker()
        tracker.record(make_heartbeat(state="RUNNING"))

        tracker.expire("STRAT-001")

        assert tracker.is_expired("STRAT-001")
        assert tracker.state("STRAT-001") == RuntimeState.UNKNOWN.value

    def test_expire_ignores_later_duplicate_until_new_record(self) -> None:
        tracker = HeartbeatTracker()
        tracker.record(make_heartbeat(state="RUNNING"))
        tracker.expire("STRAT-001")
        assert tracker.state("STRAT-001") == RuntimeState.UNKNOWN.value

        tracker.record(make_heartbeat(state="RUNNING", sequence=2))
        assert tracker.state("STRAT-001") == "RUNNING"

    def test_is_stale_respects_provided_now(self) -> None:
        tracker = HeartbeatTracker(timeout_seconds=30.0)
        tracker.record(make_heartbeat(now=utcnow()))

        reference = utcnow() + timedelta(seconds=31)
        assert tracker.is_stale("STRAT-001", now=reference)

        fresh_reference = utcnow() + timedelta(seconds=5)
        assert not tracker.is_stale("STRAT-001", now=fresh_reference)

    def test_timestamp_is_timezone_aware(self) -> None:
        assert utcnow().tzinfo is not None
        assert utcnow().tzinfo == timezone.utc
