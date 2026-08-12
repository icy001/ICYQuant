"""
ExecutionDetector — turns execution / venue signals into detections.
"""

from __future__ import annotations

from typing import List

from ..incident_scope import IncidentScope
from ..incident_severity import IncidentSeverity
from ..incident_source import IncidentSource
from ..incident_type import IncidentType
from ..detection.detection_rule import DetectionRule


class ExecutionDetector:
    """Default detection rules for execution-engine signals."""

    RULES: List[DetectionRule] = [
        DetectionRule(
            rule_id="EXECUTION-REJECTED-001",
            event_type="EXECUTION_REJECTED",
            incident_type=IncidentType.EXECUTION_FAILURE,
            severity=IncidentSeverity.HIGH,
            scope=IncidentScope.VENUE,
            source=IncidentSource.EXECUTION_ENGINE,
            priority=10,
            cooldown_seconds=300.0,
        ),
        DetectionRule(
            rule_id="EXECUTION-TIMEOUT-001",
            event_type="EXECUTION_TIMEOUT",
            incident_type=IncidentType.EXECUTION_FAILURE,
            severity=IncidentSeverity.MEDIUM,
            scope=IncidentScope.VENUE,
            source=IncidentSource.EXECUTION_ENGINE,
            priority=20,
            cooldown_seconds=300.0,
        ),
        DetectionRule(
            rule_id="ORDER-REJECTED-BY-VENUE-001",
            event_type="ORDER_REJECTED_BY_VENUE",
            incident_type=IncidentType.EXECUTION_FAILURE,
            severity=IncidentSeverity.HIGH,
            scope=IncidentScope.VENUE,
            source=IncidentSource.EXECUTION_ENGINE,
            priority=15,
            cooldown_seconds=180.0,
        ),
    ]

    @classmethod
    def build_rules(cls) -> List[DetectionRule]:
        return list(cls.RULES)
