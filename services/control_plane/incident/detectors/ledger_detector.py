"""
LedgerDetector — turns ledger signals into detections.
"""

from __future__ import annotations

from typing import List

from ..incident_scope import IncidentScope
from ..incident_severity import IncidentSeverity
from ..incident_source import IncidentSource
from ..incident_type import IncidentType
from ..detection.detection_rule import DetectionRule


class LedgerDetector:
    """Default detection rules for ledger signals."""

    RULES: List[DetectionRule] = [
        DetectionRule(
            rule_id="LEDGER-MISMATCH-001",
            event_type="LEDGER_MISMATCH",
            incident_type=IncidentType.LEDGER_INTEGRITY_FAILURE,
            severity=IncidentSeverity.CRITICAL,
            scope=IncidentScope.ACCOUNT,
            source=IncidentSource.LEDGER,
            priority=10,
            cooldown_seconds=120.0,
        ),
        DetectionRule(
            rule_id="LEDGER-ENTRY-FAILED-001",
            event_type="LEDGER_ENTRY_FAILED",
            incident_type=IncidentType.LEDGER_INTEGRITY_FAILURE,
            severity=IncidentSeverity.HIGH,
            scope=IncidentScope.ACCOUNT,
            source=IncidentSource.LEDGER,
            priority=20,
            cooldown_seconds=300.0,
        ),
    ]

    @classmethod
    def build_rules(cls) -> List[DetectionRule]:
        return list(cls.RULES)
