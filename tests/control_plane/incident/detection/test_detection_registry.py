"""DetectionRegistry — pluggable rule store."""
from __future__ import annotations

from services.control_plane.incident.detection.detection_registry import (
    DetectionRegistry,
)
from services.control_plane.incident.detection.detection_rule import DetectionRule
from services.control_plane.incident.incident_scope import IncidentScope
from services.control_plane.incident.incident_severity import IncidentSeverity
from services.control_plane.incident.incident_source import IncidentSource
from services.control_plane.incident.incident_type import IncidentType


def _rule(rule_id, event_type="SIGNAL_X", priority=100):
    return DetectionRule(
        rule_id=rule_id,
        event_type=event_type,
        incident_type=IncidentType.SYSTEM_FAILURE,
        severity=IncidentSeverity.MEDIUM,
        scope=IncidentScope.GLOBAL,
        source=IncidentSource.MANUAL,
        priority=priority,
    )


class TestRegistryLifecycle:
    def test_register_and_get(self):
        registry = DetectionRegistry()
        registry.register(_rule("R-1"))
        assert registry.get("R-1") is not None
        assert registry.get("missing") is None

    def test_unregister(self):
        registry = DetectionRegistry()
        registry.register(_rule("R-1"))
        assert registry.unregister("R-1") is True
        assert registry.unregister("R-1") is False

    def test_enable_disable(self):
        registry = DetectionRegistry()
        registry.register(_rule("R-1"))
        assert registry.disable("R-1") is True
        assert registry.get("R-1").enabled is False
        assert registry.enable("R-1") is True
        assert registry.get("R-1").enabled is True
        assert registry.disable("missing") is False

    def test_list_and_clear(self):
        registry = DetectionRegistry()
        registry.register(_rule("R-1"))
        registry.register(_rule("R-2"))
        assert registry.rule_count() == 2
        assert len(registry.list()) == 2
        registry.clear()
        assert registry.rule_count() == 0


class TestRegistryQuery:
    def test_list_for_event_type_filters_disabled(self):
        registry = DetectionRegistry()
        registry.register(_rule("R-1", event_type="A", priority=10))
        registry.register(_rule("R-2", event_type="B", priority=20))
        registry.disable("R-1")
        assert [r.rule_id for r in registry.list_for_event_type("A")] == []
        assert [r.rule_id for r in registry.list_for_event_type("B")] == ["R-2"]

    def test_list_for_event_type_sorts_by_priority_ascending(self):
        registry = DetectionRegistry()
        registry.register(_rule("R-high", event_type="A", priority=50))
        registry.register(_rule("R-top", event_type="A", priority=10))
        registry.register(_rule("R-low", event_type="A", priority=90))
        assert [r.rule_id for r in registry.list_for_event_type("A")] == [
            "R-top",
            "R-high",
            "R-low",
        ]
