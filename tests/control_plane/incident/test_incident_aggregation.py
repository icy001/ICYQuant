"""Incident aggregation — event/detection counts, severity and scope merge.

Spec sections 32 (aggregation), 33 (severity only-up), 34 (scope only-widen),
42 (storm suppression counters).
"""
from __future__ import annotations

from datetime import datetime, timezone

from services.control_plane.incident.detection.detection_result import (
    DetectionResult,
)
from services.control_plane.incident.incident import Incident
from services.control_plane.incident.incident_scope import IncidentScope
from services.control_plane.incident.incident_severity import IncidentSeverity
from services.control_plane.incident.incident_source import IncidentSource
from services.control_plane.incident.incident_type import IncidentType

NOW = datetime(2026, 8, 12, 10, 0, 0, tzinfo=timezone.utc)


def make_incident(**kwargs) -> Incident:
    defaults = dict(
        incident_id="INC-20260812-000001",
        type=IncidentType.POSITION_INTEGRITY_FAILURE,
        severity=IncidentSeverity.MEDIUM,
        scope=IncidentScope.STRATEGY,
        source=IncidentSource.POSITION_SERVICE,
        created_at=NOW,
    )
    defaults.update(kwargs)
    return Incident(**defaults)


def detection(**kwargs) -> DetectionResult:
    defaults = dict(
        matched=True,
        rule_id="R-1",
        event_id="evt-1",
        event_type="POSITION_UNTRUSTED",
        incident_type=IncidentType.POSITION_INTEGRITY_FAILURE,
        severity=IncidentSeverity.HIGH,
        scope=IncidentScope.STRATEGY,
        source=IncidentSource.POSITION_SERVICE,
        service="position-service",
        strategy="ALPHA",
        occurred_at=NOW,
    )
    defaults.update(kwargs)
    return DetectionResult(**defaults)


class TestEventAggregation:
    def test_aggregate_event_increments_counts(self):
        inc = make_incident()
        inc.aggregate_event(source="position-service", scope_id="ALPHA", now=NOW)
        inc.aggregate_event(source="position-service", scope_id="ALPHA", now=NOW)
        assert inc.event_count == 2
        assert inc.detection_count == 0

    def test_sources_and_scope_ids_deduplicate(self):
        inc = make_incident()
        inc.aggregate_event(source="position", scope_id="ALPHA", now=NOW)
        inc.aggregate_event(source="position", scope_id="ALPHA", now=NOW)
        inc.aggregate_event(source="ledger", scope_id="BETA", now=NOW)
        assert inc.source_count == 2
        assert inc.affected_scope_count == 2

    def test_suppressed_events_counted_separately(self):
        inc = make_incident()
        inc.aggregate_event(source="position", scope_id="ALPHA", now=NOW)
        inc.aggregate_event(suppressed=True, now=NOW)
        inc.aggregate_event(suppressed=True, now=NOW)
        assert inc.event_count == 1
        assert inc.suppressed_event_count == 2


class TestSeverityAggregation:
    def test_detection_raises_severity_upgrade_only(self):
        inc = make_incident(severity=IncidentSeverity.MEDIUM)
        inc.aggregate_detection(detection(severity=IncidentSeverity.CRITICAL), now=NOW)
        assert inc.severity is IncidentSeverity.CRITICAL

    def test_lower_severity_detection_never_downgrades(self):
        inc = make_incident(severity=IncidentSeverity.CRITICAL)
        inc.aggregate_detection(detection(severity=IncidentSeverity.MEDIUM), now=NOW)
        assert inc.severity is IncidentSeverity.CRITICAL

    def test_detection_counts_and_source_tracking(self):
        inc = make_incident()
        inc.aggregate_detection(detection(strategy="ALPHA"), now=NOW)
        inc.aggregate_detection(detection(strategy="BETA", event_id="evt-2"), now=NOW)
        assert inc.detection_count == 2
        assert inc.affected_scope_count == 2
        assert inc.source_count == 1


class TestScopeAggregation:
    def test_scope_expands_strategy_to_service_to_global(self):
        inc = make_incident(scope=IncidentScope.STRATEGY)
        assert inc.expand_scope(IncidentScope.SERVICE, now=NOW) is True
        assert inc.scope is IncidentScope.SERVICE
        assert inc.expand_scope(IncidentScope.GLOBAL, now=NOW) is True
        assert inc.scope is IncidentScope.GLOBAL

    def test_scope_never_shrinks(self):
        inc = make_incident(scope=IncidentScope.GLOBAL)
        assert inc.expand_scope(IncidentScope.SERVICE, now=NOW) is False
        assert inc.scope is IncidentScope.GLOBAL

    def test_detection_widens_scope(self):
        inc = make_incident(scope=IncidentScope.STRATEGY)
        inc.aggregate_detection(
            detection(scope=IncidentScope.GLOBAL, severity=IncidentSeverity.MEDIUM),
            now=NOW,
        )
        assert inc.scope is IncidentScope.GLOBAL

    def test_scope_expansion_is_auditable(self):
        inc = make_incident(scope=IncidentScope.STRATEGY)
        inc.expand_scope(IncidentScope.SERVICE, now=NOW)
        assert "STRATEGY -> SERVICE" in inc.timeline.entries[-1].detail


class TestAggregationSerialization:
    def test_round_trip_preserves_aggregation(self):
        inc = make_incident()
        inc.aggregate_event(source="position", scope_id="ALPHA", now=NOW)
        inc.aggregate_event(source="ledger", scope_id="BETA", now=NOW)
        inc.aggregate_event(suppressed=True, now=NOW)
        inc.aggregate_detection(detection(), now=NOW)

        restored = Incident.from_dict(inc.to_dict())
        assert restored.event_count == inc.event_count
        assert restored.detection_count == inc.detection_count
        assert restored.suppressed_event_count == inc.suppressed_event_count
        assert restored.source_count == inc.source_count
        assert restored.affected_scope_count == inc.affected_scope_count
        assert restored.severity is inc.severity
        assert restored.scope is inc.scope
