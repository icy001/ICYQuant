"""
ExecutionCorrelator — execution failures are often downstream of data faults.
"""

from __future__ import annotations

from typing import List

from ..correlation.correlation_rule import CorrelationRule
from ..incident_type import IncidentType


class ExecutionCorrelator:
    """Declares data faults as parents of execution failures."""

    RULES: List[CorrelationRule] = [
        CorrelationRule(
            rule_id="MARKET-DATA-EXECUTION-001",
            parent_incident_type=IncidentType.MARKET_DATA_FAILURE,
            child_incident_type=IncidentType.EXECUTION_FAILURE,
            max_window_seconds=300.0,
            confidence=0.85,
            priority=10,
            description="bad market data stops executions",
        ),
        CorrelationRule(
            rule_id="EXECUTION-RECONCILIATION-001",
            parent_incident_type=IncidentType.EXECUTION_FAILURE,
            child_incident_type=IncidentType.RECONCILIATION_FAILURE,
            max_window_seconds=600.0,
            confidence=0.70,
            priority=20,
            description="missed/duplicated executions surface at reconciliation",
        ),
    ]

    @classmethod
    def build_rules(cls) -> List[CorrelationRule]:
        return list(cls.RULES)
