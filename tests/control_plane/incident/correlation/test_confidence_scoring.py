"""CorrelationEngine — best-rule selection by confidence then priority.

Spec sections 27 (confidence) and 28 (priority as the secondary key).
"""
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
from services.control_plane.incident.incident_id import IncidentId
from services.control_plane.incident.incident_scope import IncidentScope
from services.control_plane.incident.incident_severity import IncidentSeverity
from services.control_plane.incident.incident_source import IncidentSource
from services.control_plane.incident.incident_type import IncidentType
from services.control_plane.repositories.incident_repository import (
    IncidentRepository,
)

NOW = datetime(2026, 8, 12, 10, 0, 0, tzinfo=timezone.utc)


def _active_parent(repository: IncidentRepository) -> None:
    repository.create(
        Incident(
            incident_id=IncidentId.generate(1),
            type=IncidentType.HEALTH_FAILURE,
            severity=IncidentSeverity.HIGH,
            scope=IncidentScope.SERVICE,
            source=IncidentSource.HEALTH_MONITOR,
            created_at=NOW,
            updated_at=NOW,
        )
    )


def _execution_detection() -> DetectionResult:
    return DetectionResult(
        matched=True,
        rule_id="EXEC-1",
        event_id="evt-exec",
        event_type="ORDER_REJECTED",
        incident_type=IncidentType.EXECUTION_FAILURE,
        severity=IncidentSeverity.HIGH,
        scope=IncidentScope.SERVICE,
        source=IncidentSource.EXECUTION_ENGINE,
        service="execution",
        occurred_at=NOW + timedelta(seconds=30),
    )


def _rule(rule_id: str, confidence: float, priority: int) -> CorrelationRule:
    return CorrelationRule(
        rule_id=rule_id,
        parent_incident_type=IncidentType.HEALTH_FAILURE,
        child_incident_type=IncidentType.EXECUTION_FAILURE,
        max_window_seconds=300.0,
        confidence=confidence,
        priority=priority,
    )


class TestConfidenceSelection:
    def test_highest_confidence_rule_wins(self):
        repository = IncidentRepository()
        _active_parent(repository)
        engine = CorrelationEngine(
            repository=repository,
            rules=[
                _rule("RULE-LOW", confidence=0.40, priority=10),
                _rule("RULE-HIGH", confidence=0.95, priority=50),
            ],
        )
        result = engine.correlate(_execution_detection())
        assert result.decision is CorrelationDecision.CHILD_INCIDENT
        assert "RULE-HIGH" in result.reason

    def test_priority_breaks_confidence_ties(self):
        repository = IncidentRepository()
        _active_parent(repository)
        engine = CorrelationEngine(
            repository=repository,
            rules=[
                _rule("RULE-P2", confidence=0.90, priority=20),
                _rule("RULE-P1", confidence=0.90, priority=10),
            ],
        )
        result = engine.correlate(_execution_detection())
        assert result.decision is CorrelationDecision.CHILD_INCIDENT
        assert "RULE-P1" in result.reason

    def test_low_confidence_rule_still_links_when_alone(self):
        repository = IncidentRepository()
        _active_parent(repository)
        engine = CorrelationEngine(
            repository=repository,
            rules=[_rule("RULE-ONLY", confidence=0.40, priority=10)],
        )
        result = engine.correlate(_execution_detection())
        assert result.decision is CorrelationDecision.CHILD_INCIDENT
        assert "RULE-ONLY" in result.reason

    def test_confidence_is_clamped_to_unit_range(self):
        rule = _rule("R", confidence=3.0, priority=1)
        assert rule.confidence == 1.0
        rule = _rule("R2", confidence=-1.0, priority=1)
        assert rule.confidence == 0.0

    def test_serialization_preserves_scoring(self):
        rule = _rule("R", confidence=0.75, priority=25)
        restored = CorrelationRule.from_dict(rule.to_dict())
        assert restored.confidence == 0.75
        assert restored.priority == 25
