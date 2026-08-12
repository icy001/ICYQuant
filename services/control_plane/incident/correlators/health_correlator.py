"""
HealthCorrelator — unhealthy services are root causes of many downstream faults.
"""

from __future__ import annotations

from typing import List

from ..correlation.correlation_rule import CorrelationRule
from ..incident_type import IncidentType


class HealthCorrelator:
    """Declares HEALTH_FAILURE as a parent of downstream incident types."""

    RULES: List[CorrelationRule] = [
        CorrelationRule(
            rule_id="HEALTH-EXECUTION-001",
            parent_incident_type=IncidentType.HEALTH_FAILURE,
            child_incident_type=IncidentType.EXECUTION_FAILURE,
            max_window_seconds=300.0,
            confidence=0.85,
            priority=10,
            description="an unhealthy service often causes execution failures",
        ),
        CorrelationRule(
            rule_id="HEALTH-RISK-001",
            parent_incident_type=IncidentType.HEALTH_FAILURE,
            child_incident_type=IncidentType.RISK_BREACH,
            max_window_seconds=300.0,
            confidence=0.60,
            priority=30,
            description="risk can be breached when monitoring/health degrades",
        ),
        CorrelationRule(
            rule_id="HEALTH-MARKET-DATA-001",
            parent_incident_type=IncidentType.HEALTH_FAILURE,
            child_incident_type=IncidentType.MARKET_DATA_FAILURE,
            max_window_seconds=300.0,
            confidence=0.75,
            priority=20,
            description="an unhealthy feed component degrades market data",
        ),
    ]

    @classmethod
    def build_rules(cls) -> List[CorrelationRule]:
        return list(cls.RULES)
