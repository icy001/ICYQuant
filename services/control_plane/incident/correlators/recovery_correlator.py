"""
RecoveryCorrelator — a failed recovery always refers back to its original fault.
"""

from __future__ import annotations

from typing import List

from ..correlation.correlation_rule import CorrelationRule
from ..incident_type import IncidentType


class RecoveryCorrelator:
    """Declares original fault types as parents of RECOVERY_FAILURE."""

    RULES: List[CorrelationRule] = [
        CorrelationRule(
            rule_id="HEALTH-RECOVERY-001",
            parent_incident_type=IncidentType.HEALTH_FAILURE,
            child_incident_type=IncidentType.RECOVERY_FAILURE,
            max_window_seconds=600.0,
            confidence=0.95,
            priority=10,
            description="recovery of an unhealthy component failed",
        ),
        CorrelationRule(
            rule_id="EXECUTION-RECOVERY-001",
            parent_incident_type=IncidentType.EXECUTION_FAILURE,
            child_incident_type=IncidentType.RECOVERY_FAILURE,
            max_window_seconds=600.0,
            confidence=0.95,
            priority=10,
            description="recovery of execution state failed",
        ),
        CorrelationRule(
            rule_id="POSITION-RECOVERY-001",
            parent_incident_type=IncidentType.POSITION_INTEGRITY_FAILURE,
            child_incident_type=IncidentType.RECOVERY_FAILURE,
            max_window_seconds=600.0,
            confidence=0.95,
            priority=10,
            description="position rebuild failed",
        ),
    ]

    @classmethod
    def build_rules(cls) -> List[CorrelationRule]:
        return list(cls.RULES)
