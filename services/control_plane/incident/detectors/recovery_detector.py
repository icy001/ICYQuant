"""
RecoveryDetector — turns recovery-engine signals into detections.
"""

from __future__ import annotations

from typing import List

from ..incident_scope import IncidentScope
from ..incident_severity import IncidentSeverity
from ..incident_source import IncidentSource
from ..incident_type import IncidentType
from ..detection.detection_rule import DetectionRule


class RecoveryDetector:
    """Default detection rules for recovery-engine signals."""

    RULES: List[DetectionRule] = [
        DetectionRule(
            rule_id="RECOVERY-FAILED-001",
            event_type="RECOVERY_FAILED",
            incident_type=IncidentType.RECOVERY_FAILURE,
            severity=IncidentSeverity.HIGH,
            scope=IncidentScope.GLOBAL,
            source=IncidentSource.RECOVERY_ENGINE,
            priority=10,
            cooldown_seconds=180.0,
        ),
        DetectionRule(
            rule_id="RECOVERY-TIMEOUT-001",
            event_type="RECOVERY_TIMEOUT",
            incident_type=IncidentType.RECOVERY_FAILURE,
            severity=IncidentSeverity.MEDIUM,
            scope=IncidentScope.GLOBAL,
            source=IncidentSource.RECOVERY_ENGINE,
            priority=20,
            cooldown_seconds=300.0,
        ),
        DetectionRule(
            rule_id="RECOVERY-LOOP-001",
            event_type="RECOVERY_LOOP",
            incident_type=IncidentType.RECOVERY_FAILURE,
            severity=IncidentSeverity.CRITICAL,
            scope=IncidentScope.GLOBAL,
            source=IncidentSource.RECOVERY_ENGINE,
            priority=10,
            cooldown_seconds=120.0,
        ),
    ]

    @classmethod
    def build_rules(cls) -> List[DetectionRule]:
        return list(cls.RULES)
