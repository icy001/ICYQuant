"""
Risk decision rejected event.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from ..policy_trace import RiskPolicyTrace

RISK_DECISION_REJECTED = "RISK_DECISION_REJECTED"


@dataclass(frozen=True)
class RiskDecisionRejected:
    decision_id: str
    account_id: str
    strategy_id: str
    signal_id: str
    instrument_id: str

    reason_code: str
    reason: str
    policy_id: str

    correlation_id: str
    causation_id: str
    lineage_id: str

    # Commit 41 Part 1.1: auditable decision-event payload.
    request_id: str | None = None
    decision: str = RISK_DECISION_REJECTED
    timestamp: datetime | None = None

    # Commit 41 Part 1.3: full policy evaluation context.
    policy_trace: RiskPolicyTrace | None = None

    type: str = field(default=RISK_DECISION_REJECTED, init=False, repr=False)
