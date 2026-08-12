"""Unit tests: Incident aggregate — lifecycle, severity, correlation, timeline."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from services.control_plane.incident.incident import (
    Incident,
    IncidentResolutionError,
    IncidentSeverityDowngradeError,
)
from services.control_plane.incident.incident_context import IncidentContext
from services.control_plane.incident.incident_event import IncidentEventType
from services.control_plane.incident.incident_fingerprint import IncidentFingerprint
from services.control_plane.incident.incident_id import IncidentId
from services.control_plane.incident.incident_scope import IncidentScope
from services.control_plane.incident.incident_severity import IncidentSeverity
from services.control_plane.incident.incident_source import IncidentSource
from services.control_plane.incident.incident_status import IncidentStatus
from services.control_plane.incident.incident_type import IncidentType

NOW = datetime(2026, 8, 12, 10, 0, 0, tzinfo=timezone.utc)


def make_incident(**kwargs) -> Incident:
    defaults = dict(
        incident_id="INC-20260812-000001",
        type=IncidentType.POSITION_INTEGRITY_FAILURE,
        severity=IncidentSeverity.CRITICAL,
        scope=IncidentScope.STRATEGY,
        source=IncidentSource.RECONCILIATION,
        created_at=NOW,
    )
    defaults.update(kwargs)
    return Incident(**defaults)


class TestIncidentCreation:
    def test_minimal_creation(self):
        inc = make_incident()
        assert inc.incident_id == IncidentId("INC-20260812-000001")
        assert inc.type is IncidentType.POSITION_INTEGRITY_FAILURE
        assert inc.severity is IncidentSeverity.CRITICAL
        assert inc.status is IncidentStatus.OPEN
        assert inc.scope is IncidentScope.STRATEGY
        assert inc.source is IncidentSource.RECONCILIATION
        assert inc.created_at == NOW
        assert inc.updated_at == NOW

    def test_creation_with_context_and_fingerprint(self):
        inc = make_incident(
            context=IncidentContext(strategy="ALPHA", correlation_id="CORR-1"),
            fingerprint=IncidentFingerprint(
                IncidentSource.RECONCILIATION, IncidentType.POSITION_INTEGRITY_FAILURE
            ),
        )
        assert inc.context.strategy == "ALPHA"
        assert inc.context.correlation_id == "CORR-1"
        assert inc.fingerprint is not None


class TestLifecycle:
    def test_happy_path(self):
        inc = make_incident()
        inc.acknowledge(actor="op-1", now=NOW)
        assert inc.status is IncidentStatus.ACKNOWLEDGED

        inc.start_mitigation(actor="op-1", now=NOW)
        assert inc.status is IncidentStatus.MITIGATING

        inc.resolve(
            resolution_reason="POSITION_REBUILT_AND_VERIFIED",
            resolved_by="op-1",
            verification_result="VERIFIED",
            now=NOW,
        )
        assert inc.status is IncidentStatus.RESOLVED
        assert inc.resolution_reason == "POSITION_REBUILT_AND_VERIFIED"
        assert inc.resolved_by == "op-1"
        assert inc.verification_result == "VERIFIED"
        assert inc.resolved_at == NOW

    def test_open_escalate_mitigate_resolve(self):
        inc = make_incident()
        inc.escalate(actor="system", detail="recovery failed", now=NOW)
        assert inc.status is IncidentStatus.ESCALATED
        assert inc.escalation_count == 1

        inc.start_mitigation(actor="op-1", now=NOW)
        assert inc.status is IncidentStatus.MITIGATING

        inc.resolve(
            resolution_reason="RECOVERY_VERIFIED",
            resolved_by="op-1",
            now=NOW,
        )
        assert inc.status is IncidentStatus.RESOLVED

    def test_resolve_reopen(self):
        inc = make_incident()
        inc.acknowledge(actor="op-1", now=NOW)
        inc.start_mitigation(actor="op-1", now=NOW)
        inc.resolve(
            resolution_reason="POSITION_REBUILT_AND_VERIFIED",
            resolved_by="op-1",
            now=NOW,
        )
        inc.reopen(actor="system", now=NOW)
        assert inc.status is IncidentStatus.REOPENED
        assert inc.reopen_count == 1
        assert inc.resolved_at is None

    def test_invalid_transition_raises(self):
        from services.control_plane.incident.incident_status import (
            IncidentStateTransitionError,
        )

        inc = make_incident()
        with pytest.raises(IncidentStateTransitionError):
            inc.resolve(
                resolution_reason="x",
                resolved_by="op-1",
                now=NOW,
            )  # OPEN -> RESOLVED is invalid


class TestResolutionRequirements:
    def test_resolution_requires_reason(self):
        inc = make_incident()
        inc.acknowledge(now=NOW)
        inc.start_mitigation(now=NOW)
        with pytest.raises(IncidentResolutionError):
            inc.resolve(resolution_reason="", resolved_by="op-1", now=NOW)

    def test_resolution_requires_actor(self):
        inc = make_incident()
        inc.acknowledge(now=NOW)
        inc.start_mitigation(now=NOW)
        with pytest.raises(IncidentResolutionError):
            inc.resolve(resolution_reason="done", resolved_by="", now=NOW)

    def test_reject_placeholder_reason(self):
        inc = make_incident()
        inc.acknowledge(now=NOW)
        inc.start_mitigation(now=NOW)
        with pytest.raises(IncidentResolutionError):
            inc.resolve(resolution_reason="  ", resolved_by="op-1", now=NOW)


class TestSeverityEscalation:
    def test_severity_can_escalate(self):
        inc = make_incident(severity=IncidentSeverity.MEDIUM)
        inc.raise_severity(IncidentSeverity.HIGH, actor="system", now=NOW)
        assert inc.severity is IncidentSeverity.HIGH
        inc.raise_severity(IncidentSeverity.CRITICAL, actor="system", now=NOW)
        assert inc.severity is IncidentSeverity.CRITICAL
        assert inc.escalation_count == 2

    def test_severity_downgrade_rejected(self):
        inc = make_incident(severity=IncidentSeverity.CRITICAL)
        with pytest.raises(IncidentSeverityDowngradeError):
            inc.raise_severity(IncidentSeverity.MEDIUM, actor="op-1", now=NOW)
        assert inc.severity is IncidentSeverity.CRITICAL

    def test_same_severity_is_noop(self):
        inc = make_incident(severity=IncidentSeverity.CRITICAL)
        inc.raise_severity(IncidentSeverity.CRITICAL, actor="op-1", now=NOW)
        assert inc.severity is IncidentSeverity.CRITICAL


class TestCorrelation:
    def test_policy_correlation(self):
        inc = make_incident()
        inc.bind_policy("POSITION_CRITICAL_POLICY", "v1.3")
        assert inc.context.policy_id == "POSITION_CRITICAL_POLICY"
        assert inc.context.policy_version == "v1.3"

    def test_recovery_correlation(self):
        inc = make_incident()
        inc.bind_recovery("REC-0017")
        assert inc.context.recovery_id == "REC-0017"

    def test_kill_switch_correlation(self):
        inc = make_incident()
        inc.bind_kill_switch("GLOBAL", "scope-1")
        assert inc.context.extra["kill_switch_scope"] == "GLOBAL"
        assert inc.context.extra["kill_switch_scope_id"] == "scope-1"

    def test_parent_child_and_root_cause(self):
        parent = make_incident(incident_id="INC-20260812-000001")
        child = make_incident(incident_id="INC-20260812-000002")
        parent.add_child(child.incident_id.value)
        child.set_parent(parent.incident_id.value)
        child.set_root_cause(parent.incident_id.value)
        assert parent.child_incident_ids == ["INC-20260812-000002"]
        assert child.parent_incident_id == "INC-20260812-000001"
        assert child.root_cause_incident_id == "INC-20260812-000001"


class TestTimelineAndEvents:
    def test_lifecycle_records_timeline(self):
        inc = make_incident()
        inc.acknowledge(actor="op-1", now=NOW)
        inc.start_mitigation(actor="op-1", now=NOW)
        inc.resolve(
            resolution_reason="POSITION_REBUILT_AND_VERIFIED",
            resolved_by="op-1",
            now=NOW,
        )
        event_types = [e.event_type for e in inc.timeline]
        assert event_types == [
            IncidentStatus.ACKNOWLEDGED.value,
            IncidentStatus.MITIGATING.value,
            IncidentEventType.INCIDENT_RESOLVED.value,
        ]

    def test_lifecycle_records_events(self):
        inc = make_incident()
        inc.acknowledge(actor="op-1", now=NOW)
        inc.escalate(actor="system", now=NOW)
        event_types = [e.event_type for e in inc.events]
        assert event_types == [
            IncidentEventType.INCIDENT_ACKNOWLEDGED,
            IncidentEventType.INCIDENT_ESCALATED,
        ]

    def test_resolution_timeline_carries_reason(self):
        inc = make_incident()
        inc.acknowledge(now=NOW)
        inc.start_mitigation(now=NOW)
        inc.resolve(
            resolution_reason="POSITION_REBUILT_AND_VERIFIED",
            resolved_by="op-1",
            now=NOW,
        )
        last = inc.timeline.entries[-1]
        assert "POSITION_REBUILT_AND_VERIFIED" in last.detail


class TestMetrics:
    def test_duration_until_resolution(self):
        created = datetime(2026, 8, 12, 10, 0, 0, tzinfo=timezone.utc)
        resolved = datetime(2026, 8, 12, 10, 2, 30, tzinfo=timezone.utc)
        inc = make_incident(created_at=created)
        inc.acknowledge(now=created)
        inc.start_mitigation(now=created)
        inc.resolve(
            resolution_reason="POSITION_REBUILT_AND_VERIFIED",
            resolved_by="op-1",
            now=resolved,
        )
        assert inc.duration == 150.0


class TestSerialization:
    def test_round_trip(self):
        inc = make_incident(
            context=IncidentContext(strategy="ALPHA", correlation_id="CORR-1"),
            fingerprint=IncidentFingerprint(
                IncidentSource.RECONCILIATION, IncidentType.POSITION_INTEGRITY_FAILURE
            ),
        )
        inc.acknowledge(actor="op-1", now=NOW)
        inc.start_mitigation(actor="op-1", now=NOW)
        inc.resolve(
            resolution_reason="POSITION_REBUILT_AND_VERIFIED",
            resolved_by="op-1",
            now=NOW,
        )
        restored = Incident.from_dict(inc.to_dict())
        assert restored.incident_id == inc.incident_id
        assert restored.type is inc.type
        assert restored.severity is inc.severity
        assert restored.status is inc.status
        assert restored.resolution_reason == inc.resolution_reason
        assert restored.context.strategy == "ALPHA"
        assert restored.fingerprint == inc.fingerprint
        assert [e.event_type for e in restored.timeline] == [
            e.event_type for e in inc.timeline
        ]
        assert len(restored.events) == len(inc.events)

    def test_repr(self):
        inc = make_incident()
        assert "INC-20260812-000001" in repr(inc)
