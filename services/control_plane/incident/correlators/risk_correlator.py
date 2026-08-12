"""
RiskCorrelator — a risk breach usually precedes integrity failures.
"""

from __future__ import annotations

from typing import List

from ..correlation.correlation_rule import CorrelationRule
from ..incident_type import IncidentType


class RiskCorrelator:
    """Declares RISK_BREACH as a parent of integrity failures."""

    RULES: List[CorrelationRule] = [
        CorrelationRule(
            rule_id="RISK-POSITION-001",
            parent_incident_type=IncidentType.RISK_BREACH,
            child_incident_type=IncidentType.POSITION_INTEGRITY_FAILURE,
            max_window_seconds=600.0,
            confidence=0.80,
            priority=10,
            description="a breached risk limit can poison position state",
        ),
        CorrelationRule(
            rule_id="RISK-LEDGER-001",
            parent_incident_type=IncidentType.RISK_BREACH,
            child_incident_type=IncidentType.LEDGER_INTEGRITY_FAILURE,
            max_window_seconds=600.0,
            confidence=0.70,
            priority=20,
            description="a breached risk limit can poison ledger state",
        ),
    ]

    @classmethod
    def build_rules(cls) -> List[CorrelationRule]:
        return list(cls.RULES)
