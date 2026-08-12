"""IncidentDetectionEngine — event -> detection pipeline."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from services.control_plane.incident.detection.detection_engine import (
    IncidentDetectionEngine,
)
from services.control_plane.incident.detection.detection_registry import (
    DetectionRegistry,
)
from services.control_plane.incident.detection.detection_rule import (
    DetectionRule,
    field_equals,
)
from services.control_plane.incident.incident_scope import IncidentScope
from services.control_plane.incident.incident_severity import IncidentSeverity
from services.control_plane.incident.incident_source import IncidentSource
from services.control_plane.incident.incident_type import IncidentType


def _rule(rule_id="R-1", event_type="SIGNAL_X", **kwargs):
    return DetectionRule(
        rule_id=rule_id,
        event_type=event_type,
        incident_type=kwargs.pop("incident_type", IncidentType.SYSTEM_FAILURE),
        severity=kwargs.pop("severity", IncidentSeverity.MEDIUM),
        scope=kwargs.pop("scope", IncidentScope.GLOBAL),
        source=kwargs.pop("source", IncidentSource.MANUAL),
        condition=kwargs.pop("condition", None),
        priority=kwargs.pop("priority", 100),
        cooldown_seconds=kwargs.pop("cooldown_seconds", None),
    )


def _event(event_type="SIGNAL_X", event_id="evt-1", **kwargs):
    data = {
        "event_type": event_type,
        "event_id": event_id,
        "occurred_at": "2026-08-12T10:00:00+00:00",
        "service": "gateway",
    }
    data.update(kwargs)
    return data


class TestEngineMatching:
    def test_matched_detection_carries_rule_metadata(self):
        registry = DetectionRegistry()
        registry.register(
            _rule(rule_id="R-1", event_type="HEALTH_DOWN",
                  incident_type=IncidentType.HEALTH_FAILURE,
                  severity=IncidentSeverity.HIGH,
                  scope=IncidentScope.SERVICE,
                  source=IncidentSource.HEALTH_MONITOR)
        )
        engine = IncidentDetectionEngine(registry=registry)
        result = engine.evaluate(
            _event(event_type="HEALTH_DOWN", service="gateway")
        )
        assert result.matched is True
        assert result.rule_id == "R-1"
        assert result.incident_type is IncidentType.HEALTH_FAILURE
        assert result.severity is IncidentSeverity.HIGH
        assert result.service == "gateway"
        assert result.suppressed is False

    def test_unmatched_event_returns_unmatched(self):
        engine = IncidentDetectionEngine()
        result = engine.evaluate(_event(event_type="UNKNOWN"))
        assert result.matched is False
        assert result.suppressed is False

    def test_condition_gates_match(self):
        registry = DetectionRegistry()
        registry.register(_rule(condition=field_equals("state", "DOWN")))
        engine = IncidentDetectionEngine(registry=registry)
        assert engine.evaluate(_event(state="DOWN")).matched is True
        assert engine.evaluate(_event(state="UP")).matched is False


class TestEventIdDeduplication:
    def test_duplicate_event_id_is_suppressed(self):
        engine = IncidentDetectionEngine()
        first = engine.evaluate(_event(event_id="evt-dup"))
        second = engine.evaluate(_event(event_id="evt-dup"))
        assert first.matched is False
        assert second.matched is False
        assert second.suppressed is True
        assert second.suppression_reason == "duplicate event_id"

    def test_event_id_reused_after_window_is_allowed(self):
        engine = IncidentDetectionEngine(dedupe_window_seconds=60.0)
        old = datetime(2026, 8, 12, 10, 0, 0, tzinfo=timezone.utc)
        later = old + timedelta(seconds=120)
        engine.evaluate(_event(event_id="evt-1", occurred_at=old.isoformat()))
        second = engine.evaluate(
            _event(event_id="evt-1", occurred_at=later.isoformat())
        )
        assert second.matched is False  # no rules -> still unmatched
        assert second.suppressed is False

    def test_clear_resets_deduplication(self):
        engine = IncidentDetectionEngine()
        engine.evaluate(_event(event_id="evt-1"))
        engine.clear()
        result = engine.evaluate(_event(event_id="evt-1"))
        assert result.suppressed is False


class TestRuleCooldown:
    def test_cooldown_suppresses_repeat_fires(self):
        registry = DetectionRegistry()
        registry.register(_rule(cooldown_seconds=60.0))
        engine = IncidentDetectionEngine(registry=registry)
        first = engine.evaluate(_event(event_id="evt-1"))
        second = engine.evaluate(_event(event_id="evt-2"))
        assert first.matched is True
        assert second.matched is False
        assert second.suppressed is True
        assert second.suppression_reason == "rule cooldown active"

    def test_no_cooldown_allows_repeat_fires(self):
        registry = DetectionRegistry()
        registry.register(_rule(cooldown_seconds=None))
        engine = IncidentDetectionEngine(registry=registry)
        assert engine.evaluate(_event(event_id="evt-1")).matched is True
        assert engine.evaluate(_event(event_id="evt-2")).matched is True
