"""
RiskDetector — turns risk-engine signals into detections.
"""

from __future__ import annotations

from typing import List

from ..incident_scope import IncidentScope
from ..incident_severity import IncidentSeverity
from ..incident_source import IncidentSource
from ..incident_type import IncidentType
from ..detection.detection_rule import DetectionRule, field_in


class RiskDetector:
    """Default detection rules for risk-engine signals."""

    RULES: List[DetectionRule] = [
        DetectionRule(
            rule_id="RISK-LIMIT-BREACH-001",
            event_type="RISK_LIMIT_BREACHED",
            incident_type=IncidentType.RISK_BREACH,
            severity=IncidentSeverity.CRITICAL,
            scope=IncidentScope.STRATEGY,
            source=IncidentSource.RISK_ENGINE,
            condition=field_in("severity", {"HIGH", "CRITICAL"}),
            priority=10,
            cooldown_seconds=120.0,
        ),
        DetectionRule(
            rule_id="RISK-DRAWDOWN-BREACH-001",
            event_type="RISK_DRAWDOWN_BREACHED",
            incident_type=IncidentType.RISK_BREACH,
            severity=IncidentSeverity.HIGH,
            scope=IncidentScope.STRATEGY,
            source=IncidentSource.RISK_ENGINE,
            priority=20,
            cooldown_seconds=300.0,
        ),
        DetectionRule(
            rule_id="RISK-MARGIN-SHORTFALL-001",
            event_type="MARGIN_SHORTFALL",
            incident_type=IncidentType.RISK_BREACH,
            severity=IncidentSeverity.HIGH,
            scope=IncidentScope.ACCOUNT,
            source=IncidentSource.RISK_ENGINE,
            priority=20,
            cooldown_seconds=300.0,
        ),
    ]

    @classmethod
    def build_rules(cls) -> List[DetectionRule]:
        return list(cls.RULES)
