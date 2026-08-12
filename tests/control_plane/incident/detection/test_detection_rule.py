"""DetectionRule — matching semantics and serialization."""
from __future__ import annotations

from services.control_plane.incident.detection.detection_rule import (
    DetectionRule,
    field_equals,
    field_in,
)
from services.control_plane.incident.incident_scope import IncidentScope
from services.control_plane.incident.incident_severity import IncidentSeverity
from services.control_plane.incident.incident_source import IncidentSource
from services.control_plane.incident.incident_type import IncidentType


def _rule(**kwargs):
    return DetectionRule(
        rule_id=kwargs.pop("rule_id", "RULE-001"),
        event_type=kwargs.pop("event_type", "SIGNAL_X"),
        incident_type=kwargs.pop("incident_type", IncidentType.SYSTEM_FAILURE),
        severity=kwargs.pop("severity", IncidentSeverity.MEDIUM),
        scope=kwargs.pop("scope", IncidentScope.GLOBAL),
        source=kwargs.pop("source", IncidentSource.MANUAL),
        condition=kwargs.pop("condition", None),
        enabled=kwargs.pop("enabled", True),
        priority=kwargs.pop("priority", 100),
        cooldown_seconds=kwargs.pop("cooldown_seconds", None),
    )


class TestDetectionRuleMatching:
    def test_matches_by_event_type_without_condition(self):
        assert _rule().matches({"event_type": "SIGNAL_X"})

    def test_rejects_wrong_event_type(self):
        assert not _rule().matches({"event_type": "OTHER"})

    def test_field_equals_condition(self):
        rule = _rule(condition=field_equals("state", "DOWN"))
        assert rule.matches({"event_type": "SIGNAL_X", "state": "DOWN"})
        assert not rule.matches({"event_type": "SIGNAL_X", "state": "UP"})

    def test_field_in_condition(self):
        rule = _rule(condition=field_in("severity", {"HIGH", "CRITICAL"}))
        assert rule.matches({"event_type": "SIGNAL_X", "severity": "CRITICAL"})
        assert not rule.matches({"event_type": "SIGNAL_X", "severity": "LOW"})

    def test_disabled_rule_never_matches(self):
        assert not _rule(enabled=False).matches({"event_type": "SIGNAL_X"})


class TestDetectionRuleDefaultsAndSerialization:
    def test_defaults(self):
        rule = _rule()
        assert rule.rule_version == "v1"
        assert rule.priority == 100
        assert rule.source is IncidentSource.MANUAL
        assert rule.cooldown_seconds is None

    def test_serialization_roundtrip(self):
        rule = _rule(condition=field_equals("state", "DOWN"), cooldown_seconds=60.0)
        restored = DetectionRule.from_dict(rule.to_dict())
        assert restored.rule_id == rule.rule_id
        assert restored.event_type == rule.event_type
        assert restored.incident_type == rule.incident_type
        assert restored.severity == rule.severity
        assert restored.scope == rule.scope
        assert restored.source == rule.source
        assert restored.enabled is True
        assert restored.priority == rule.priority
        assert restored.cooldown_seconds == 60.0

    def test_serialization_drops_condition(self):
        rule = _rule(condition=field_equals("state", "DOWN"))
        restored = DetectionRule.from_dict(rule.to_dict())
        assert restored.condition is None
