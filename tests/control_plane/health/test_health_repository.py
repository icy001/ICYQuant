"""Unit tests: HealthRepository — heartbeat idempotency, records, incidents."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from services.control_plane.events.heartbeat_missed import HeartbeatMissed
from services.control_plane.health.health_incident import (
    HealthIncident,
    HealthIncidentState,
)
from services.control_plane.health.health_status import HealthStatus
from services.control_plane.health.heartbeat import Heartbeat
from services.control_plane.repositories.health_repository import (
    HealthRecord,
    HealthRepository,
)

NOW = datetime(2026, 8, 12, 10, 0, 0, tzinfo=timezone.utc)


def hb(sequence=100, component_id="risk_engine", instance_id="risk-01", ts=None):
    return Heartbeat(
        component_id=component_id,
        instance_id=instance_id,
        sequence=sequence,
        timestamp=ts or NOW,
    )


class TestHeartbeatPersistence:
    def test_save_and_read_last(self):
        repo = HealthRepository()
        repo.save_heartbeat(hb(sequence=100))
        repo.save_heartbeat(hb(sequence=101))
        last = repo.get_last_heartbeat("risk_engine")
        assert last is not None
        assert last.sequence == 101
        assert repo.heartbeat_count() == 1  # one instance → one row

    def test_idempotent_duplicate(self):
        repo = HealthRepository()
        assert repo.save_heartbeat(hb(sequence=100)) is True
        assert repo.save_heartbeat(hb(sequence=100)) is False
        assert repo.save_heartbeat(hb(sequence=99)) is False  # out of order
        assert repo.heartbeat_count() == 1

    def test_instance_identity(self):
        repo = HealthRepository()
        repo.save_heartbeat(hb(sequence=100, component_id="position", instance_id="position-01"))
        repo.save_heartbeat(hb(sequence=100, component_id="position", instance_id="position-02"))
        assert repo.heartbeat_count() == 2
        assert (
            repo.get_last_heartbeat("position", instance_id="position-02").instance_id
            == "position-02"
        )

    def test_per_instance_last_heartbeat(self):
        repo = HealthRepository()
        repo.save_heartbeat(hb(sequence=10, component_id="position", instance_id="p1"))
        repo.save_heartbeat(hb(sequence=20, component_id="position", instance_id="p2"))
        assert repo.get_last_heartbeat("position").instance_id == "p2"


class TestHealthRecords:
    def test_save_and_get_record(self):
        repo = HealthRepository()
        record = HealthRecord(
            component_id="risk_engine",
            status=HealthStatus.UNHEALTHY,
            score=12.5,
            updated_at=NOW,
            details={"reason": "HEARTBEAT_CRITICAL_TIMEOUT"},
        )
        repo.save_record(record)
        loaded = repo.get_record("risk_engine")
        assert loaded is not None
        assert loaded.status is HealthStatus.UNHEALTHY
        assert loaded.score == 12.5
        assert loaded.details["reason"] == "HEARTBEAT_CRITICAL_TIMEOUT"

    def test_missing_record_is_none(self):
        repo = HealthRepository()
        assert repo.get_record("nope") is None

    def test_record_serializes(self):
        record = HealthRecord(
            component_id="x", status=HealthStatus.HEALTHY, score=100.0, updated_at=NOW
        )
        data = record.to_dict()
        assert data["status"] == "HEALTHY"


class TestHealthEvents:
    def test_append_and_list(self):
        repo = HealthRepository()
        event = HeartbeatMissed(component_id="risk_engine", detected_at=NOW)
        repo.append_event(event)
        assert repo.event_count() == 1
        assert repo.list_events()[0] is event


class TestHealthIncidents:
    def test_save_and_get(self):
        repo = HealthRepository()
        incident = HealthIncident(
            incident_id="INC-00001",
            component_id="position-service",
            severity="HIGH",
            reason="DATA_STALE",
            state=HealthIncidentState.OPEN,
            started_at=NOW,
        )
        repo.save_incident(incident)
        loaded = repo.get_incident("position-service")
        assert loaded is not None
        assert loaded.incident_id == "INC-00001"
        assert repo.incident_count() == 1

    def test_clear(self):
        repo = HealthRepository()
        repo.save_heartbeat(hb())
        repo.save_incident(
            HealthIncident(
                incident_id="INC-1", component_id="x", severity="LOW", reason="R"
            )
        )
        repo.clear()
        assert repo.heartbeat_count() == 0
        assert repo.incident_count() == 0
        assert repo.event_count() == 0
