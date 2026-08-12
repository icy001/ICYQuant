"""Built-in detectors and correlators — rule coverage."""
from __future__ import annotations

from services.control_plane.incident.correlation.correlation_rule import (
    CorrelationRule,
)
from services.control_plane.incident.correlators import (
    ALL_CORRELATORS,
    build_default_rules,
)
from services.control_plane.incident.detection.detection_registry import (
    DetectionRegistry,
)
from services.control_plane.incident.detection.detection_rule import DetectionRule
from services.control_plane.incident.detectors import (
    ALL_DETECTORS,
    register_default_rules,
)


class TestDetectors:
    def test_eight_detectors_registered(self):
        assert len(ALL_DETECTORS) == 8

    def test_every_detector_builds_valid_rules(self):
        for detector in ALL_DETECTORS:
            rules = detector.build_rules()
            assert rules, f"{detector.__name__} must own at least one rule"
            for rule in rules:
                assert isinstance(rule, DetectionRule)
                assert rule.rule_id
                assert rule.event_type
                assert rule.incident_type is not None
                assert rule.severity is not None
                assert rule.source is not None

    def test_register_default_rules(self):
        registry = DetectionRegistry()
        count = register_default_rules(registry)
        assert count > 0
        assert registry.rule_count() == count
        assert len(registry.list()) == count

    def test_default_rules_are_discoverable_by_event_type(self):
        registry = DetectionRegistry()
        register_default_rules(registry)
        for rule in registry.list():
            assert registry.list_for_event_type(rule.event_type)


class TestCorrelators:
    def test_six_correlators_registered(self):
        assert len(ALL_CORRELATORS) == 6

    def test_every_correlator_builds_valid_rules(self):
        for correlator in ALL_CORRELATORS:
            rules = correlator.build_rules()
            assert rules, f"{correlator.__name__} must own at least one rule"
            for rule in rules:
                assert isinstance(rule, CorrelationRule)
                assert rule.rule_id
                assert rule.parent_incident_type is not None
                assert rule.child_incident_type is not None
                assert rule.max_window_seconds > 0

    def test_build_default_rules(self):
        rules = build_default_rules()
        assert len(rules) > 0
        assert all(isinstance(r, CorrelationRule) for r in rules)
