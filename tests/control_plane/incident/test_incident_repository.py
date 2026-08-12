"""Unit tests: IncidentRepository persistence and queries."""

from __future__ import annotations

from datetime import datetime, timezone

from services.control_plane.incident.incident import Incident
from services.control_plane.incident.incident_fingerprint import IncidentFingerprint
from services.control_plane.incident.incident_scope import IncidentScope
from services.control_plane.incident.incident_severity import IncidentSeverity
from services.control_plane.incident.incident_source import IncidentSource
from services.control_plane.incident.incident_type import IncidentType
from services.control_plane.repositories.incident_repository import IncidentRepository

NOW = datetime(2026, 8, 12, 10, 0, 0, tzinfo=timezone.utc)


def build(
    iid: str,
    itype=IncidentType.POSITION_INTEGRITY_FAILURE,
    severity=IncidentSeverity.CRITICAL,
    scope=IncidentScope.STRATEGY,
    source=IncidentSource.RECONCILIATION,
) -> Incident:
    return Incident(
        incident_id=iid,
        type=itype,
        severity=severity,
        scope=scope,
        source=source,
        created_at=NOW,
    )


class TestPersistence:
    def test_save_and_get(self):
        repo = IncidentRepository()
        inc = build("INC-20260812-000001")
        repo.save(inc)
        assert repo.incident_count() == 1
        fetched = repo.get("INC-20260812-000001")
        assert fetched is not None
        assert fetched.incident_id.value == "INC-20260812-000001"

    def test_get_missing_returns_none(self):
        repo = IncidentRepository()
        assert repo.get("INC-20260812-999999") is None

    def test_save_is_upsert(self):
        repo = IncidentRepository()
        inc = build("INC-20260812-000001")
        repo.save(inc)
        inc.acknowledge(actor="op-1", now=NOW)
        repo.save(inc)
        assert repo.incident_count() == 1
        assert repo.get("INC-20260812-000001").status.value == "ACKNOWLEDGED"

    def test_update_after_creation(self):
        repo = IncidentRepository()
        inc = build("INC-20260812-000001")
        repo.create(inc)
        inc.acknowledge(actor="op-1", now=NOW)
        inc.start_mitigation(actor="op-1", now=NOW)
        inc.resolve(
            resolution_reason="POSITION_REBUILT_AND_VERIFIED",
            resolved_by="op-1",
            now=NOW,
        )
        repo.update(inc)
        assert repo.get("INC-20260812-000001").status.value == "RESOLVED"


class TestQueries:
    def test_find_open(self):
        repo = IncidentRepository()
        repo.save(build("INC-20260812-000001"))
        resolved = build("INC-20260812-000002")
        resolved.acknowledge(now=NOW)
        resolved.start_mitigation(now=NOW)
        resolved.resolve(
            resolution_reason="POSITION_REBUILT_AND_VERIFIED",
            resolved_by="op-1",
            now=NOW,
        )
        repo.save(resolved)
        open_ids = {i.incident_id.value for i in repo.find_open()}
        assert open_ids == {"INC-20260812-000001"}

    def test_find_by_severity(self):
        repo = IncidentRepository()
        repo.save(build("INC-20260812-000001", severity=IncidentSeverity.CRITICAL))
        repo.save(build("INC-20260812-000002", severity=IncidentSeverity.HIGH))
        critical = repo.find_by_severity(IncidentSeverity.CRITICAL)
        assert [i.incident_id.value for i in critical] == ["INC-20260812-000001"]

    def test_find_by_scope(self):
        repo = IncidentRepository()
        repo.save(build("INC-20260812-000001", scope=IncidentScope.STRATEGY))
        repo.save(build("INC-20260812-000002", scope=IncidentScope.GLOBAL))
        assert len(repo.find_by_scope(IncidentScope.STRATEGY)) == 1
        assert len(repo.find_by_scope(IncidentScope.GLOBAL)) == 1

    def test_critical_count_only_open(self):
        repo = IncidentRepository()
        repo.save(build("INC-20260812-000001", severity=IncidentSeverity.CRITICAL))
        resolved = build("INC-20260812-000002", severity=IncidentSeverity.FATAL)
        resolved.acknowledge(now=NOW)
        resolved.start_mitigation(now=NOW)
        resolved.resolve(
            resolution_reason="x", resolved_by="op-1", now=NOW
        )
        repo.save(resolved)
        assert repo.critical_count() == 1


class TestDeduplication:
    def test_find_active_by_fingerprint(self):
        repo = IncidentRepository()
        fp = IncidentFingerprint(
            IncidentSource.RECONCILIATION,
            IncidentType.POSITION_INTEGRITY_FAILURE,
            IncidentScope.STRATEGY,
            "ALPHA",
        )
        inc = build("INC-20260812-000001")
        inc.fingerprint = fp
        repo.save(inc)
        assert repo.find_active_by_fingerprint(fp) is not None

    def test_find_active_ignores_resolved(self):
        repo = IncidentRepository()
        fp = IncidentFingerprint(
            IncidentSource.RECONCILIATION,
            IncidentType.POSITION_INTEGRITY_FAILURE,
        )
        inc = build("INC-20260812-000001")
        inc.fingerprint = fp
        inc.acknowledge(now=NOW)
        inc.start_mitigation(now=NOW)
        inc.resolve(
            resolution_reason="POSITION_REBUILT_AND_VERIFIED",
            resolved_by="op-1",
            now=NOW,
        )
        repo.save(inc)
        assert repo.find_active_by_fingerprint(fp) is None
        assert len(repo.find_by_fingerprint(fp)) == 1

    def test_incident_storm_aggregates_to_one(self):
        # 100 detections of the same fault → 1 incident, 100 detection events.
        repo = IncidentRepository()
        fp = IncidentFingerprint(
            IncidentSource.HEALTH_MONITOR,
            IncidentType.HEALTH_FAILURE,
            IncidentScope.SERVICE,
            "event-bus",
        )
        first = build("INC-20260812-000001", itype=IncidentType.HEALTH_FAILURE, source=IncidentSource.HEALTH_MONITOR, scope=IncidentScope.SERVICE)
        first.fingerprint = fp
        repo.save(first)
        for i in range(100):
            repo.append_event(f"detection-{i}")
        assert repo.incident_count() == 1
        assert repo.event_count() == 100


class TestEventAudit:
    def test_events_are_retained(self):
        repo = IncidentRepository()
        from services.control_plane.events.incident_created import IncidentCreated

        repo.append_event(
            IncidentCreated(
                incident_id="INC-20260812-000001",
                type=IncidentType.POSITION_INTEGRITY_FAILURE,
                severity=IncidentSeverity.CRITICAL,
                scope=IncidentScope.GLOBAL,
                source=IncidentSource.RECONCILIATION,
            )
        )
        assert repo.event_count() == 1
        assert repo.list_events()[0].event_type == "INCIDENT_CREATED"

    def test_clear(self):
        repo = IncidentRepository()
        repo.save(build("INC-20260812-000001"))
        repo.append_event("e1")
        repo.clear()
        assert repo.incident_count() == 0
        assert repo.event_count() == 0
