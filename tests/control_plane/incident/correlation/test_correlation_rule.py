"""CorrelationRule — declarative parent/child relationships."""
from __future__ import annotations

from services.control_plane.incident.correlation.correlation_rule import (
    CorrelationRule,
)
from services.control_plane.incident.incident_type import IncidentType


class TestCorrelationRule:
    def test_matches_declared_parent_child(self):
        rule = CorrelationRule(
            rule_id="R-1",
            parent_incident_type=IncidentType.HEALTH_FAILURE,
            child_incident_type=IncidentType.EXECUTION_FAILURE,
            max_window_seconds=300.0,
        )
        assert rule.matches(
            IncidentType.HEALTH_FAILURE,
            IncidentType.EXECUTION_FAILURE,
        )
        assert not rule.matches(
            IncidentType.EXECUTION_FAILURE,
            IncidentType.HEALTH_FAILURE,
        )

    def test_matches_child(self):
        rule = CorrelationRule(
            rule_id="R-1",
            parent_incident_type=IncidentType.HEALTH_FAILURE,
            child_incident_type=IncidentType.EXECUTION_FAILURE,
        )
        assert rule.matches_child(IncidentType.EXECUTION_FAILURE)
        assert not rule.matches_child(IncidentType.HEALTH_FAILURE)
        assert not rule.matches_child(None)

    def test_disabled_rule_never_matches(self):
        rule = CorrelationRule(
            rule_id="R-1",
            parent_incident_type=IncidentType.HEALTH_FAILURE,
            child_incident_type=IncidentType.EXECUTION_FAILURE,
            enabled=False,
        )
        assert not rule.matches(
            IncidentType.HEALTH_FAILURE,
            IncidentType.EXECUTION_FAILURE,
        )
        assert not rule.matches_child(IncidentType.EXECUTION_FAILURE)

    def test_accepts_string_types(self):
        rule = CorrelationRule(
            rule_id="R-1",
            parent_incident_type="HEALTH_FAILURE",
            child_incident_type="EXECUTION_FAILURE",
        )
        assert rule.parent_incident_type is IncidentType.HEALTH_FAILURE
        assert rule.matches(IncidentType.HEALTH_FAILURE, "EXECUTION_FAILURE")

    def test_serialization_roundtrip(self):
        rule = CorrelationRule(
            rule_id="R-1",
            parent_incident_type=IncidentType.HEALTH_FAILURE,
            child_incident_type=IncidentType.EXECUTION_FAILURE,
            max_window_seconds=120.0,
            confidence=0.85,
            priority=15,
            description="unhealthy service breaks executions",
        )
        restored = CorrelationRule.from_dict(rule.to_dict())
        assert restored == rule

    def test_serialization_roundtrip_without_scoring(self):
        rule = CorrelationRule(
            rule_id="R-1",
            parent_incident_type=IncidentType.HEALTH_FAILURE,
            child_incident_type=IncidentType.EXECUTION_FAILURE,
        )
        restored = CorrelationRule.from_dict(rule.to_dict())
        assert restored == rule
        assert restored.confidence == 1.0
        assert restored.priority == 100

    def test_confidence_defaults_and_clamping(self):
        rule = CorrelationRule(
            rule_id="R-1",
            parent_incident_type=IncidentType.HEALTH_FAILURE,
            child_incident_type=IncidentType.EXECUTION_FAILURE,
        )
        assert rule.confidence == 1.0
        assert rule.priority == 100

        rule = CorrelationRule(
            rule_id="R-2",
            parent_incident_type=IncidentType.HEALTH_FAILURE,
            child_incident_type=IncidentType.EXECUTION_FAILURE,
            confidence=1.5,
        )
        assert rule.confidence == 1.0

        rule = CorrelationRule(
            rule_id="R-3",
            parent_incident_type=IncidentType.HEALTH_FAILURE,
            child_incident_type=IncidentType.EXECUTION_FAILURE,
            confidence=-0.5,
        )
        assert rule.confidence == 0.0
