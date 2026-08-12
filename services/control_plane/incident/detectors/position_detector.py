"""
PositionDetector — turns position-service signals into detections.
"""

from __future__ import annotations

from typing import List

from ..incident_scope import IncidentScope
from ..incident_severity import IncidentSeverity
from ..incident_source import IncidentSource
from ..incident_type import IncidentType
from ..detection.detection_rule import DetectionRule, field_equals


class PositionDetector:
    """Default detection rules for position-service signals."""

    RULES: List[DetectionRule] = [
        DetectionRule(
            rule_id="POSITION-UNTRUSTED-001",
            event_type="POSITION_HEALTH_CHANGED",
            incident_type=IncidentType.POSITION_INTEGRITY_FAILURE,
            severity=IncidentSeverity.CRITICAL,
            scope=IncidentScope.STRATEGY,
            source=IncidentSource.POSITION_SERVICE,
            condition=field_equals("state", "UNTRUSTED"),
            priority=10,
            cooldown_seconds=120.0,
        ),
        DetectionRule(
            rule_id="POSITION-MISMATCH-001",
            event_type="POSITION_MISMATCH",
            incident_type=IncidentType.POSITION_INTEGRITY_FAILURE,
            severity=IncidentSeverity.HIGH,
            scope=IncidentScope.STRATEGY,
            source=IncidentSource.POSITION_SERVICE,
            priority=20,
            cooldown_seconds=300.0,
        ),
    ]

    @classmethod
    def build_rules(cls) -> List[DetectionRule]:
        return list(cls.RULES)
