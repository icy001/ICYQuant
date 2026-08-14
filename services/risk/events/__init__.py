"""
Risk events package.

Backward-compatible exports:

- ``RiskAuditEvent`` (legacy flat-module symbol, kept for compatibility)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .risk_decision_approved import (
    RISK_DECISION_APPROVED,
    RiskDecisionApproved,
)
from .risk_decision_rejected import (
    RISK_DECISION_REJECTED,
    RiskDecisionRejected,
)


@dataclass(frozen=True)
class RiskAuditEvent:
    order_id: str
    account_id: str
    decision: str
    rule: str | None
    reason: str | None
    created_at: datetime


__all__ = [
    "RISK_DECISION_APPROVED",
    "RISK_DECISION_REJECTED",
    "RiskAuditEvent",
    "RiskDecisionApproved",
    "RiskDecisionRejected",
]
