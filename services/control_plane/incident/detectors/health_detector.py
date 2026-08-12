"""
HealthDetector — turns health-monitor signals into detections.
"""

from __future__ import annotations

from typing import Any, Dict, List

from ..incident_scope import IncidentScope
from ..incident_severity import IncidentSeverity
from ..incident_source import IncidentSource
from ..incident_type import IncidentType
from ..detection.detection_rule import DetectionRule, field_equals


class HealthDetector:
    """Default detection rules for health-monitor signals."""

    RULES: List[DetectionRule] = [
        DetectionRule(
            rule_id="HEALTH-MONITOR-DOWN-001",
            event_type="HEALTH_MONITOR_DOWN",
            incident_type=IncidentType.HEALTH_FAILURE,
            severity=IncidentSeverity.HIGH,
            scope=IncidentScope.SERVICE,
            source=IncidentSource.HEALTH_MONITOR,
            condition=field_equals("state", "DOWN"),
            priority=10,
            cooldown_seconds=300.0,
        ),
        DetectionRule(
            rule_id="HEALTH-SERVICE-RESTARTING-001",
            event_type="SERVICE_RESTARTING",
            incident_type=IncidentType.HEALTH_FAILURE,
            severity=IncidentSeverity.MEDIUM,
            scope=IncidentScope.SERVICE,
            source=IncidentSource.HEALTH_MONITOR,
            priority=20,
            cooldown_seconds=600.0,
        ),
        DetectionRule(
            rule_id="HEALTH-CHECK-FAILED-001",
            event_type="HEALTH_CHECK_FAILED",
            incident_type=IncidentType.HEALTH_FAILURE,
            severity=IncidentSeverity.MEDIUM,
            scope=IncidentScope.SERVICE,
            source=IncidentSource.HEALTH_MONITOR,
            priority=30,
            cooldown_seconds=300.0,
        ),
    ]

    @classmethod
    def build_rules(cls) -> List[DetectionRule]:
        return list(cls.RULES)
