"""
IncidentSource — where the incident was detected.

Source and type are two independent dimensions: a POSITION_INTEGRITY_FAILURE
can be reported by POSITION_SERVICE, RECONCILIATION or a manual operator
(spec section 8).
"""

from __future__ import annotations

from enum import Enum


class IncidentSource(str, Enum):
    HEALTH_MONITOR = "HEALTH_MONITOR"
    RISK_ENGINE = "RISK_ENGINE"
    POSITION_SERVICE = "POSITION_SERVICE"
    LEDGER = "LEDGER"
    RECONCILIATION = "RECONCILIATION"
    EVENT_BUS = "EVENT_BUS"
    EXECUTION_ENGINE = "EXECUTION_ENGINE"
    POLICY_ENGINE = "POLICY_ENGINE"
    RECOVERY_ENGINE = "RECOVERY_ENGINE"
    MANUAL = "MANUAL"
