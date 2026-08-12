"""
ReconciliationDetector — turns reconciliation signals into detections.
"""

from __future__ import annotations

from typing import List

from ..incident_scope import IncidentScope
from ..incident_severity import IncidentSeverity
from ..incident_source import IncidentSource
from ..incident_type import IncidentType
from ..detection.detection_rule import DetectionRule


class ReconciliationDetector:
    """Default detection rules for reconciliation signals."""

    RULES: List[DetectionRule] = [
        DetectionRule(
            rule_id="RECONCILIATION-MISMATCH-001",
            event_type="RECONCILIATION_MISMATCH",
            incident_type=IncidentType.RECONCILIATION_FAILURE,
            severity=IncidentSeverity.HIGH,
            scope=IncidentScope.ACCOUNT,
            source=IncidentSource.RECONCILIATION,
            priority=10,
            cooldown_seconds=300.0,
        ),
        DetectionRule(
            rule_id="RECONCILIATION-TIMEOUT-001",
            event_type="RECONCILIATION_TIMEOUT",
            incident_type=IncidentType.RECONCILIATION_FAILURE,
            severity=IncidentSeverity.MEDIUM,
            scope=IncidentScope.ACCOUNT,
            source=IncidentSource.RECONCILIATION,
            priority=20,
            cooldown_seconds=600.0,
        ),
    ]

    @classmethod
    def build_rules(cls) -> List[DetectionRule]:
        return list(cls.RULES)
