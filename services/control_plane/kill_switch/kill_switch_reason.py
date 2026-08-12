"""
KillSwitchReason — why a kill switch was activated.

Manual reasons:

    EMERGENCY                 operator emergency halt
    OPERATOR_ACTION           explicit operator decision

Automatic reasons (spec section 39):

    RISK_SYSTEM_FAILURE           risk engine critical failure
    EVENT_BUS_CRITICAL_FAILURE    event bus critical failure
    EXECUTION_ENGINE_CRITICAL_FAILURE  execution engine critical failure
    POSITION_INTEGRITY_FAILURE    position integrity check failed
    RECONCILIATION_FAILURE        global reconciliation failed

Kill Switch activation is high-risk: reason, actor and scope are required.
"""

from __future__ import annotations

from enum import Enum


class KillSwitchReason(str, Enum):
    EMERGENCY = "EMERGENCY"
    RISK_SYSTEM_FAILURE = "RISK_SYSTEM_FAILURE"
    EVENT_BUS_CRITICAL_FAILURE = "EVENT_BUS_CRITICAL_FAILURE"
    EXECUTION_ENGINE_CRITICAL_FAILURE = "EXECUTION_ENGINE_CRITICAL_FAILURE"
    POSITION_INTEGRITY_FAILURE = "POSITION_INTEGRITY_FAILURE"
    RECONCILIATION_FAILURE = "RECONCILIATION_FAILURE"
    OPERATOR_ACTION = "OPERATOR_ACTION"

    @property
    def is_automatic(self) -> bool:
        return self not in (KillSwitchReason.EMERGENCY, KillSwitchReason.OPERATOR_ACTION)
