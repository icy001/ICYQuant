"""
EventBusDetector — turns event-bus signals into detections.
"""

from __future__ import annotations

from typing import List

from ..incident_scope import IncidentScope
from ..incident_severity import IncidentSeverity
from ..incident_source import IncidentSource
from ..incident_type import IncidentType
from ..detection.detection_rule import DetectionRule


class EventBusDetector:
    """Default detection rules for event-bus signals."""

    RULES: List[DetectionRule] = [
        DetectionRule(
            rule_id="EVENT-BUS-DISCONNECTED-001",
            event_type="EVENT_BUS_DISCONNECTED",
            incident_type=IncidentType.EVENT_BUS_FAILURE,
            severity=IncidentSeverity.CRITICAL,
            scope=IncidentScope.GLOBAL,
            source=IncidentSource.EVENT_BUS,
            priority=10,
            cooldown_seconds=60.0,
        ),
        DetectionRule(
            rule_id="EVENT-BUS-LAG-001",
            event_type="EVENT_BUS_LAG",
            incident_type=IncidentType.EVENT_BUS_FAILURE,
            severity=IncidentSeverity.MEDIUM,
            scope=IncidentScope.GLOBAL,
            source=IncidentSource.EVENT_BUS,
            priority=20,
            cooldown_seconds=300.0,
        ),
        DetectionRule(
            rule_id="EVENT-DELIVERY-FAILED-001",
            event_type="EVENT_DELIVERY_FAILED",
            incident_type=IncidentType.EVENT_BUS_FAILURE,
            severity=IncidentSeverity.HIGH,
            scope=IncidentScope.GLOBAL,
            source=IncidentSource.EVENT_BUS,
            priority=15,
            cooldown_seconds=180.0,
        ),
    ]

    @classmethod
    def build_rules(cls) -> List[DetectionRule]:
        return list(cls.RULES)
