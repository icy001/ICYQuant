"""
Audit Context — contextual information for a governance audit event.

Captures the state of the system at the moment an audit event is recorded,
including the decision, policy, authority, and market snapshots that
were active at that point in time.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AuditContext:
    """Rich context for a governance audit event.

    Contains all relevant state snapshots that were active when
    the audited action occurred.
    """

    correlation_id: str = ""
    causation_id: str = ""

    # Decision context
    decision_id: str = ""
    decision_type: str = ""
    decision_source: str = ""

    # Policy context
    policy_id: str = ""
    policy_version: str = ""
    policy_hash: str = ""

    # Authority context
    authority_id: str = ""
    delegation_id: str = ""

    # Approval context
    approval_id: str = ""
    approval_status: str = ""

    # Execution context
    order_id: str = ""
    trade_id: str = ""
    execution_id: str = ""

    # State before/after
    before_state: Optional[Dict[str, Any]] = None
    after_state: Optional[Dict[str, Any]] = None

    # Business metadata
    amount: float = 0.0
    scope: str = ""
    risk_score: float = 0.0
    instrument: str = ""

    # Tags for flexible filtering
    tags: Dict[str, str] = field(default_factory=dict)

    # Timing
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "decision_id": self.decision_id,
            "decision_type": self.decision_type,
            "decision_source": self.decision_source,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "policy_hash": self.policy_hash,
            "authority_id": self.authority_id,
            "delegation_id": self.delegation_id,
            "approval_id": self.approval_id,
            "approval_status": self.approval_status,
            "order_id": self.order_id,
            "trade_id": self.trade_id,
            "execution_id": self.execution_id,
            "before_state": self.before_state,
            "after_state": self.after_state,
            "amount": self.amount,
            "scope": self.scope,
            "risk_score": self.risk_score,
            "instrument": self.instrument,
            "tags": self.tags,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuditContext":
        return cls(
            correlation_id=data.get("correlation_id", ""),
            causation_id=data.get("causation_id", ""),
            decision_id=data.get("decision_id", ""),
            decision_type=data.get("decision_type", ""),
            decision_source=data.get("decision_source", ""),
            policy_id=data.get("policy_id", ""),
            policy_version=data.get("policy_version", ""),
            policy_hash=data.get("policy_hash", ""),
            authority_id=data.get("authority_id", ""),
            delegation_id=data.get("delegation_id", ""),
            approval_id=data.get("approval_id", ""),
            approval_status=data.get("approval_status", ""),
            order_id=data.get("order_id", ""),
            trade_id=data.get("trade_id", ""),
            execution_id=data.get("execution_id", ""),
            before_state=data.get("before_state"),
            after_state=data.get("after_state"),
            amount=data.get("amount", 0.0),
            scope=data.get("scope", ""),
            risk_score=data.get("risk_score", 0.0),
            instrument=data.get("instrument", ""),
            tags=data.get("tags", {}),
            timestamp=data.get("timestamp", time.time()),
        )
