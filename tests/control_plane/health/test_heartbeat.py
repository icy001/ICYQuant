"""Unit tests: Heartbeat creation, sequence, idempotency, instance identity."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from services.control_plane.health.heartbeat import Heartbeat, HeartbeatStatus

NOW = datetime(2026, 8, 12, 10, 0, 0, tzinfo=timezone.utc)


def make_hb(
    component_id="risk_engine",
    instance_id="risk-01",
    sequence=100,
    timestamp=NOW,
    status=HeartbeatStatus.HEALTHY,
    version="0.4.0",
    metadata=None,
):
    return Heartbeat(
        component_id=component_id,
        instance_id=instance_id,
        sequence=sequence,
        timestamp=timestamp,
        status=status,
        version=version,
        metadata=metadata or {},
    )


class TestHeartbeatCreation:
    def test_fields(self):
        hb = make_hb()
        assert hb.component_id == "risk_engine"
        assert hb.instance_id == "risk-01"
        assert hb.sequence == 100
        assert hb.timestamp == NOW
        assert hb.status is HeartbeatStatus.HEALTHY
        assert hb.version == "0.4.0"

    def test_default_status_is_healthy(self):
        hb = Heartbeat(component_id="risk_engine", instance_id="risk-01", sequence=1)
        assert hb.status is HeartbeatStatus.HEALTHY

    def test_default_timestamp_is_utc_aware(self):
        hb = Heartbeat(component_id="a", instance_id="b", sequence=1)
        assert hb.timestamp.tzinfo is not None


class TestHeartbeatSequence:
    def test_identity_contains_component_instance_sequence(self):
        hb = make_hb()
        assert hb.identity == ("risk_engine", "risk-01", 100)

    def test_sequence_gap_is_detectable(self):
        hb1 = make_hb(sequence=1001)
        hb2 = make_hb(sequence=1002)
        hb3 = make_hb(sequence=1005)
        assert hb3.sequence - hb2.sequence == 3  # gap between 1002 and 1005

    def test_age(self):
        hb = make_hb(timestamp=NOW)
        assert hb.age(now=NOW + timedelta(seconds=5)) == 5.0
        assert hb.age(now=NOW + timedelta(seconds=20)) == 20.0


class TestHeartbeatIdempotency:
    def test_duplicate_identity(self):
        hb1 = make_hb()
        hb2 = make_hb()
        assert hb1.is_duplicate_of(hb2)
        assert hb1.identity == hb2.identity

    def test_same_component_different_sequence_is_not_duplicate(self):
        hb1 = make_hb(sequence=100)
        hb2 = make_hb(sequence=101)
        assert not hb1.is_duplicate_of(hb2)

    def test_stale_sequence_detection(self):
        hb1 = make_hb(sequence=100)
        hb2 = make_hb(sequence=99)
        assert hb2.is_stale_sequence(hb1)
        assert not hb1.is_stale_sequence(hb2)

    def test_same_sequence_received_twice_does_not_advance(self):
        hb1 = make_hb(sequence=10231)
        hb2 = make_hb(sequence=10231)
        # identity equality is the idempotency key
        assert hb1.identity == hb2.identity


class TestInstanceIdentity:
    def test_two_instances_have_distinct_identities(self):
        hb1 = make_hb(instance_id="position-01", sequence=100)
        hb2 = make_hb(instance_id="position-02", sequence=100)
        assert hb1.identity != hb2.identity
        assert not hb1.is_duplicate_of(hb2)

    def test_same_sequence_across_instances_is_not_duplicate(self):
        hb1 = make_hb(instance_id="position-01", sequence=100)
        hb2 = make_hb(instance_id="position-02", sequence=100)
        assert hb1.is_duplicate_of(hb2) is False


class TestHeartbeatSerialization:
    def test_roundtrip(self):
        hb = make_hb(status=HeartbeatStatus.DEGRADED, metadata={"cpu": 0.9})
        restored = Heartbeat.from_dict(hb.to_dict())
        assert restored == hb
        assert restored.identity == hb.identity

    def test_from_dict_defaults(self):
        restored = Heartbeat.from_dict(
            {"component_id": "x", "instance_id": "y", "sequence": 1}
        )
        assert restored.status is HeartbeatStatus.HEALTHY
        assert restored.timestamp.tzinfo is not None
