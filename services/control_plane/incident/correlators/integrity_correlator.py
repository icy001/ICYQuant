"""
IntegrityCorrelator — integrity failures cascade across the bookkeeping chain.
"""

from __future__ import annotations

from typing import List

from ..correlation.correlation_rule import CorrelationRule
from ..incident_type import IncidentType


class IntegrityCorrelator:
    """Declares parent/child links between integrity-related incident types."""

    RULES: List[CorrelationRule] = [
        CorrelationRule(
            rule_id="POSITION-LEDGER-001",
            parent_incident_type=IncidentType.POSITION_INTEGRITY_FAILURE,
            child_incident_type=IncidentType.LEDGER_INTEGRITY_FAILURE,
            max_window_seconds=600.0,
            confidence=0.90,
            priority=10,
            description="a position error usually surfaces in the ledger too",
        ),
        CorrelationRule(
            rule_id="LEDGER-RECONCILIATION-001",
            parent_incident_type=IncidentType.LEDGER_INTEGRITY_FAILURE,
            child_incident_type=IncidentType.RECONCILIATION_FAILURE,
            max_window_seconds=900.0,
            confidence=0.95,
            priority=10,
            description="ledger mismatches are caught by reconciliation",
        ),
    ]

    @classmethod
    def build_rules(cls) -> List[CorrelationRule]:
        return list(cls.RULES)
