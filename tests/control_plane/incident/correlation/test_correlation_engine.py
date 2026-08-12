"""CorrelationEngine — new / existing / child / none decisions."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from services.control_plane.incident.correlation.correlation_engine import (
    CorrelationEngine,
)
from services.control_plane.incident.correlation.correlation_result import (
    CorrelationDecision,
)
from services.control_plane.incident.correlation.correlation_rule import (
    CorrelationRule,
)
from services.control_plane.incident.detection.detection_result import (
    DetectionResult,
)
from services.control_plane.incident.incident import Incident
from services.control_plane.incident.incident_fingerprint import IncidentFingerprint
from services.control_plane.incident.incident_id import IncidentId
from services.control_plane.incident.incident_scope import IncidentScope
from services.control_plane.incident.incident_severity import IncidentSeverity
from services.control_plane.incident.incident_source import IncidentSource
from services.control_plane.incident.incident_status import IncidentStatus
from services.control_plane.incident.incident_type import IncidentType
from services.control_plane.repositories.incident_repository import IncidentRepository

NOW = datetime(2026, 8, 12, 10, 0, 0, tzinfo=timezone.utc)


def _detection(**kwargs):
    return DetectionResult(
        matched=kwargs.pop("matched", True),
        rule_id=kwargs.pop("rule_id", "R-1"),
        event_id=kwargs.pop("event_id", "evt-1"),
        event_type=kwargs.pop("event_type", "HEALTH_MONITOR_DOWN"),
        incident_type=kwargs.pop("incident_type", IncidentType.HEALTH_FAILURE),
        severity=kwargs.pop("severity", IncidentSeverity.HIGH),
        scope=kwargs.pop("scope", IncidentScope.SERVICE),
        source=kwargs.pop("source", IncidentSource.HEALTH_MONITOR),
        service=kwargs.pop("service", "gateway"),
        occurred_at=kwargs.pop("occurred_at", NOW),
    )


def _parent(fingerprint=None, created_at=NOW, updated_at=None, status=IncidentStatus.OPEN):
    return Incident(
        incident_id=IncidentId.generate(1),
        type=IncidentType.HEALTH_FAILURE,
        severity=IncidentSeverity.HIGH,
        scope=IncidentScope.SERVICE,
        source=IncidentSource.HEALTH_MONITOR,
        status=status,
        fingerprint=fingerprint,
        created_at=created_at,
        updated_at=updated_at or created_at,
    )


class TestNoIncident:
    def test_unmatched_detection_never_creates_incident(self):
        engine = CorrelationEngine(repository=IncidentRepository())
        result = engine.correlate(DetectionResult.unmatched("SIGNAL_X"))
        assert result.decision is CorrelationDecision.NO_INCIDENT
        assert result.fingerprint == ""
        assert result.incident_id is None


class TestNewIncident:
    def test_matched_detection_with_no_active_incident(self):
        engine = CorrelationEngine(repository=IncidentRepository())
        result = engine.correlate(_detection())
        assert result.decision is CorrelationDecision.NEW_INCIDENT
        assert result.fingerprint
        assert result.incident_type == "HEALTH_FAILURE"
        assert result.incident_id is None


class TestExistingIncident:
    def test_same_fingerprint_returns_existing(self):
        repository = IncidentRepository()
        repository.create(
            _parent(
                fingerprint=IncidentFingerprint(
                    source=IncidentSource.HEALTH_MONITOR,
                    incident_type=IncidentType.HEALTH_FAILURE,
                    scope=IncidentScope.SERVICE,
                    scope_id="gateway",
                )
            )
        )
        engine = CorrelationEngine(repository=repository)
        result = engine.correlate(_detection())
        assert result.decision is CorrelationDecision.EXISTING_INCIDENT
        assert result.incident_id == "INC-20260812-000001"
        assert result.parent_incident_id is None


class TestChildIncident:
    def test_child_attached_when_parent_active(self):
        repository = IncidentRepository()
        repository.create(_parent())
        rule = CorrelationRule(
            rule_id="HEALTH-EXEC-001",
            parent_incident_type=IncidentType.HEALTH_FAILURE,
            child_incident_type=IncidentType.EXECUTION_FAILURE,
            max_window_seconds=300.0,
        )
        engine = CorrelationEngine(repository=repository, rules=[rule])
        detection = _detection(
            event_type="EXECUTION_REJECTED",
            incident_type=IncidentType.EXECUTION_FAILURE,
            source=IncidentSource.EXECUTION_ENGINE,
            service="execution",
            occurred_at=NOW + timedelta(seconds=60),
        )
        result = engine.correlate(detection)
        assert result.decision is CorrelationDecision.CHILD_INCIDENT
        assert result.parent_incident_id == "INC-20260812-000001"

    def test_no_child_when_parent_outside_window(self):
        repository = IncidentRepository()
        repository.create(_parent(created_at=NOW - timedelta(hours=2)))
        rule = CorrelationRule(
            rule_id="HEALTH-EXEC-001",
            parent_incident_type=IncidentType.HEALTH_FAILURE,
            child_incident_type=IncidentType.EXECUTION_FAILURE,
            max_window_seconds=300.0,
        )
        engine = CorrelationEngine(repository=repository, rules=[rule])
        detection = _detection(
            event_type="EXECUTION_REJECTED",
            incident_type=IncidentType.EXECUTION_FAILURE,
            source=IncidentSource.EXECUTION_ENGINE,
            service="execution",
        )
        result = engine.correlate(detection)
        assert result.decision is CorrelationDecision.NEW_INCIDENT

    def test_no_child_when_parent_closed(self):
        repository = IncidentRepository()
        repository.create(
            _parent(
                status=IncidentStatus.CLOSED,
            )
        )
        rule = CorrelationRule(
            rule_id="HEALTH-EXEC-001",
            parent_incident_type=IncidentType.HEALTH_FAILURE,
            child_incident_type=IncidentType.EXECUTION_FAILURE,
            max_window_seconds=300.0,
        )
        engine = CorrelationEngine(repository=repository, rules=[rule])
        detection = _detection(
            event_type="EXECUTION_REJECTED",
            incident_type=IncidentType.EXECUTION_FAILURE,
            source=IncidentSource.EXECUTION_ENGINE,
            service="execution",
        )
        result = engine.correlate(detection)
        assert result.decision is CorrelationDecision.NEW_INCIDENT


class TestRuleManagement:
    def test_add_and_remove_rule(self):
        engine = CorrelationEngine(repository=IncidentRepository())
        rule = CorrelationRule("R-1", IncidentType.HEALTH_FAILURE, IncidentType.EXECUTION_FAILURE)
        engine.add_rule(rule)
        assert engine.rule_count() == 1
        assert engine.remove_rule("R-1") is True
        assert engine.rule_count() == 0
        assert engine.remove_rule("R-1") is False

    def test_serialization(self):
        engine = CorrelationEngine(repository=IncidentRepository())
        engine.add_rule(
            CorrelationRule("R-1", IncidentType.HEALTH_FAILURE, IncidentType.EXECUTION_FAILURE)
        )
        data = engine.to_dict()
        assert data["window_seconds"] == engine.window_seconds
        assert len(data["rules"]) == 1
