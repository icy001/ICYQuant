"""IncidentPipeline — Detection -> Correlation -> Incident application layer.

Spec sections 16 (detection never mutates incidents directly), 19 (same
fingerprint -> same incident), 29 (event id dedup), 41 (child escalation),
42 (storm suppression counters).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from services.control_plane.incident.correlation.correlation_engine import (
    CorrelationEngine,
)
from services.control_plane.incident.correlation.correlation_rule import (
    CorrelationRule,
)
from services.control_plane.incident.detection.detection_engine import (
    IncidentDetectionEngine,
)
from services.control_plane.incident.detection.detection_registry import (
    DetectionRegistry,
)
from services.control_plane.incident.detection.detection_rule import DetectionRule
from services.control_plane.incident.incident import Incident
from services.control_plane.incident.incident_pipeline import IncidentPipeline
from services.control_plane.incident.incident_scope import IncidentScope
from services.control_plane.incident.incident_severity import IncidentSeverity
from services.control_plane.incident.incident_source import IncidentSource
from services.control_plane.incident.incident_type import IncidentType
from services.control_plane.repositories.incident_repository import (
    IncidentRepository,
)

NOW = datetime(2026, 8, 12, 10, 0, 0, tzinfo=timezone.utc)


def _make_pipeline(rules=None, cooldown_seconds=None):
    registry = DetectionRegistry()
    registry.register(
        DetectionRule(
            rule_id="POS-A",
            event_type="POSITION_UNTRUSTED",
            incident_type=IncidentType.POSITION_INTEGRITY_FAILURE,
            severity=IncidentSeverity.MEDIUM,
            scope=IncidentScope.STRATEGY,
            source=IncidentSource.POSITION_SERVICE,
            priority=10,
            cooldown_seconds=cooldown_seconds,
        )
    )
    registry.register(
        DetectionRule(
            rule_id="POS-B",
            event_type="POSITION_VERSION_MISMATCH",
            incident_type=IncidentType.POSITION_INTEGRITY_FAILURE,
            severity=IncidentSeverity.CRITICAL,
            scope=IncidentScope.STRATEGY,
            source=IncidentSource.POSITION_SERVICE,
            priority=10,
        )
    )
    registry.register(
        DetectionRule(
            rule_id="HLTH-1",
            event_type="HEALTH_MONITOR_DOWN",
            incident_type=IncidentType.HEALTH_FAILURE,
            severity=IncidentSeverity.HIGH,
            scope=IncidentScope.SERVICE,
            source=IncidentSource.HEALTH_MONITOR,
            priority=10,
        )
    )
    registry.register(
        DetectionRule(
            rule_id="EXEC-1",
            event_type="ORDER_REJECTED",
            incident_type=IncidentType.EXECUTION_FAILURE,
            severity=IncidentSeverity.CRITICAL,
            scope=IncidentScope.SERVICE,
            source=IncidentSource.EXECUTION_ENGINE,
            priority=10,
        )
    )
    repository = IncidentRepository()
    detection_engine = IncidentDetectionEngine(registry=registry)
    correlation_engine = CorrelationEngine(
        repository=repository, rules=list(rules) if rules else []
    )
    pipeline = IncidentPipeline(
        repository=repository,
        detection_engine=detection_engine,
        correlation_engine=correlation_engine,
    )
    return pipeline, repository


def _position_event(event_id, event_type, occurred_at):
    return {
        "event_id": event_id,
        "event_type": event_type,
        "service": "position-service",
        "strategy": "ALPHA",
        "occurred_at": occurred_at,
    }


class TestCreation:
    def test_normal_event_creates_no_incident(self):
        pipeline, repository = _make_pipeline()
        result = pipeline.ingest(
            {
                "event_id": "evt-ok",
                "event_type": "HEALTH_CHECK_OK",
                "service": "gateway",
                "occurred_at": NOW,
            }
        )
        assert result is None
        assert repository.incident_count() == 0

    def test_matched_event_opens_incident(self):
        pipeline, repository = _make_pipeline()
        incident = pipeline.ingest(
            _position_event("evt-1", "POSITION_UNTRUSTED", NOW)
        )
        assert isinstance(incident, Incident)
        assert incident.type is IncidentType.POSITION_INTEGRITY_FAILURE
        assert incident.severity is IncidentSeverity.MEDIUM
        assert incident.event_count == 1
        assert incident.detection_count == 1
        assert incident.fingerprint is not None
        assert repository.incident_count() == 1


class TestAggregation:
    def test_repeat_fingerprint_aggregates_into_same_incident(self):
        pipeline, repository = _make_pipeline()
        first = pipeline.ingest(
            _position_event("evt-1", "POSITION_UNTRUSTED", NOW)
        )
        second = pipeline.ingest(
            _position_event("evt-2", "POSITION_VERSION_MISMATCH", NOW + timedelta(seconds=1))
        )
        assert first.incident_id == second.incident_id
        assert second.event_count == 2
        assert second.detection_count == 2
        # §33: a CRITICAL detection raises the whole incident.
        assert second.severity is IncidentSeverity.CRITICAL
        assert repository.incident_count() == 1

    def test_duplicate_event_id_is_idempotent(self):
        pipeline, repository = _make_pipeline()
        event = _position_event("evt-dup", "POSITION_UNTRUSTED", NOW)
        first = pipeline.ingest(event)
        assert first is not None
        second = pipeline.ingest(event)
        assert second is None
        assert first.event_count == 1
        assert repository.incident_count() == 1


class TestStormControl:
    def test_cooldown_suppressed_detection_counts_as_noise(self):
        pipeline, repository = _make_pipeline(cooldown_seconds=300.0)
        first = pipeline.ingest(
            _position_event("evt-1", "POSITION_UNTRUSTED", NOW)
        )
        assert first is not None
        second = pipeline.ingest(
            _position_event("evt-2", "POSITION_UNTRUSTED", NOW + timedelta(seconds=1))
        )
        assert second is not None
        assert second.event_count == 1
        assert second.suppressed_event_count == 1
        assert repository.incident_count() == 1


class TestChildCorrelation:
    def test_child_incident_linked_to_parent(self):
        pipeline, repository = _make_pipeline(
            rules=[
                CorrelationRule(
                    rule_id="HEALTH-EXEC-001",
                    parent_incident_type=IncidentType.HEALTH_FAILURE,
                    child_incident_type=IncidentType.EXECUTION_FAILURE,
                    max_window_seconds=300.0,
                    confidence=0.95,
                    priority=10,
                )
            ]
        )
        parent = pipeline.ingest(
            {
                "event_id": "evt-h",
                "event_type": "HEALTH_MONITOR_DOWN",
                "service": "gateway",
                "occurred_at": NOW,
            }
        )
        child = pipeline.ingest(
            {
                "event_id": "evt-e",
                "event_type": "ORDER_REJECTED",
                "service": "execution",
                "occurred_at": NOW + timedelta(seconds=5),
            }
        )
        assert parent is not None and child is not None
        assert child.parent_incident_id == parent.incident_id.value
        refreshed_parent = repository.get(parent.incident_id)
        assert refreshed_parent.child_incident_ids == [child.incident_id.value]
        assert repository.incident_count() == 2

    def test_critical_child_escalates_parent_severity(self):
        pipeline, repository = _make_pipeline(
            rules=[
                CorrelationRule(
                    rule_id="HEALTH-EXEC-001",
                    parent_incident_type=IncidentType.HEALTH_FAILURE,
                    child_incident_type=IncidentType.EXECUTION_FAILURE,
                    max_window_seconds=300.0,
                )
            ]
        )
        parent = pipeline.ingest(
            {
                "event_id": "evt-h",
                "event_type": "HEALTH_MONITOR_DOWN",
                "service": "gateway",
                "occurred_at": NOW,
            }
        )
        child = pipeline.ingest(
            {
                "event_id": "evt-e",
                "event_type": "ORDER_REJECTED",
                "service": "execution",
                "occurred_at": NOW + timedelta(seconds=5),
            }
        )
        # parent starts HIGH, child is CRITICAL -> the whole family escalates
        # (spec section 41).
        assert parent.severity is IncidentSeverity.HIGH
        assert child.severity is IncidentSeverity.CRITICAL
        refreshed = repository.get(parent.incident_id)
        assert refreshed.severity is IncidentSeverity.CRITICAL
