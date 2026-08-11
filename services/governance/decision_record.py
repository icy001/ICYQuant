"""
Decision Record — complete, immutable record of a governance decision.

A DecisionRecord captures everything about a decision:
  - WHAT was decided
  - WHO made the decision
  - WHY (reasons + evidence)
  - WHAT STATE existed at the time (snapshot)
  - WHAT RULES were applied (policy, authority, approval)

This is the primary auditable artifact in the governance system.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional

from .decision_reason import DecisionReason
from .decision_evidence import DecisionEvidence
from .decision_snapshot import DecisionSnapshot
from .audit_hash import AuditHash


class DecisionRecordStatus(Enum):
    """Status of a decision record."""

    CREATED = auto()
    EVALUATING = auto()
    PENDING_APPROVAL = auto()
    APPROVED = auto()
    REJECTED = auto()
    OVERRIDDEN = auto()
    EXECUTED = auto()
    CANCELLED = auto()
    EXPIRED = auto()
    INVALIDATED = auto()


@dataclass
class DecisionRecord:
    """Complete, auditable record of a governance decision.

    This is the master object that ties together:
      Decision → Reasons → Evidence → Snapshot → Policy → Authority → Approval → Execution
    """

    record_id: str
    decision_id: str
    correlation_id: str = ""

    # ── What ──
    decision_type: str = ""     # e.g. CAPITAL_ALLOCATION, RISK_REDUCTION
    decision_source: str = ""   # e.g. AUTONOMOUS_ALLOCATOR, RISK_CONTROLLER
    instrument: str = ""
    side: str = ""              # BUY, SELL
    quantity: float = 0.0
    price: float = 0.0
    amount: float = 0.0
    status: DecisionRecordStatus = DecisionRecordStatus.CREATED

    # ── Why ──
    reasons: List[DecisionReason] = field(default_factory=list)
    evidence: Optional[DecisionEvidence] = None

    # ── State ──
    snapshot: Optional[DecisionSnapshot] = None

    # ── Governance ──
    policy_id: str = ""
    policy_version: str = ""
    policy_verdict: str = ""    # ALLOW, REVIEW, BLOCK
    authority_id: str = ""
    delegation_id: str = ""
    approval_id: str = ""
    approval_status: str = ""

    # ── Execution ──
    order_id: str = ""
    execution_id: str = ""
    trade_id: str = ""

    # ── Certification ──
    certificate_id: str = ""
    certificate_hash: str = ""

    # ── Override tracking ──
    original_decision_id: str = ""  # If this is an override
    override_reason: str = ""
    override_actor: str = ""

    # ── Integrity ──
    record_hash: str = ""
    record_version: int = 1

    timestamps: Dict[str, float] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.record_id:
            self.record_id = f"REC-{uuid.uuid4().hex[:12].upper()}"
        if not self.correlation_id:
            self.correlation_id = f"CORR-{uuid.uuid4().hex[:8].upper()}"

    def set_status(self, status: DecisionRecordStatus) -> None:
        self.status = status
        self.timestamps[status.name] = time.time()
        self.updated_at = time.time()

    def is_terminal(self) -> bool:
        return self.status in (
            DecisionRecordStatus.EXECUTED,
            DecisionRecordStatus.REJECTED,
            DecisionRecordStatus.CANCELLED,
            DecisionRecordStatus.EXPIRED,
        )

    def compute_hash(self) -> str:
        data = {
            "record_id": self.record_id,
            "decision_id": self.decision_id,
            "decision_type": self.decision_type,
            "instrument": self.instrument,
            "side": self.side,
            "quantity": self.quantity,
            "amount": self.amount,
            "status": self.status.name,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "policy_verdict": self.policy_verdict,
            "authority_id": self.authority_id,
            "approval_id": self.approval_id,
            "created_at": self.created_at,
        }
        self.record_hash = AuditHash.compute_snapshot_hash(data)
        return self.record_hash

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "decision_id": self.decision_id,
            "correlation_id": self.correlation_id,
            "decision_type": self.decision_type,
            "decision_source": self.decision_source,
            "instrument": self.instrument,
            "side": self.side,
            "quantity": self.quantity,
            "price": self.price,
            "amount": self.amount,
            "status": self.status.name,
            "reasons": [r.to_dict() for r in self.reasons],
            "evidence": self.evidence.to_dict() if self.evidence else None,
            "snapshot": self.snapshot.to_dict() if self.snapshot else None,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "policy_verdict": self.policy_verdict,
            "authority_id": self.authority_id,
            "delegation_id": self.delegation_id,
            "approval_id": self.approval_id,
            "approval_status": self.approval_status,
            "order_id": self.order_id,
            "execution_id": self.execution_id,
            "trade_id": self.trade_id,
            "certificate_id": self.certificate_id,
            "certificate_hash": self.certificate_hash,
            "original_decision_id": self.original_decision_id,
            "override_reason": self.override_reason,
            "override_actor": self.override_actor,
            "record_hash": self.record_hash,
            "record_version": self.record_version,
            "timestamps": self.timestamps,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DecisionRecord":
        status = data.get("status", "CREATED")
        if isinstance(status, str):
            status = DecisionRecordStatus[status]

        reasons = [
            DecisionReason.from_dict(r)
            for r in data.get("reasons", [])
        ]
        evidence = DecisionEvidence.from_dict(data["evidence"]) if data.get("evidence") else None
        snapshot = DecisionSnapshot.from_dict(data["snapshot"]) if data.get("snapshot") else None

        return cls(
            record_id=data.get("record_id", ""),
            decision_id=data.get("decision_id", ""),
            correlation_id=data.get("correlation_id", ""),
            decision_type=data.get("decision_type", ""),
            decision_source=data.get("decision_source", ""),
            instrument=data.get("instrument", ""),
            side=data.get("side", ""),
            quantity=data.get("quantity", 0.0),
            price=data.get("price", 0.0),
            amount=data.get("amount", 0.0),
            status=status,
            reasons=reasons,
            evidence=evidence,
            snapshot=snapshot,
            policy_id=data.get("policy_id", ""),
            policy_version=data.get("policy_version", ""),
            policy_verdict=data.get("policy_verdict", ""),
            authority_id=data.get("authority_id", ""),
            delegation_id=data.get("delegation_id", ""),
            approval_id=data.get("approval_id", ""),
            approval_status=data.get("approval_status", ""),
            order_id=data.get("order_id", ""),
            execution_id=data.get("execution_id", ""),
            trade_id=data.get("trade_id", ""),
            certificate_id=data.get("certificate_id", ""),
            certificate_hash=data.get("certificate_hash", ""),
            original_decision_id=data.get("original_decision_id", ""),
            override_reason=data.get("override_reason", ""),
            override_actor=data.get("override_actor", ""),
            record_hash=data.get("record_hash", ""),
            record_version=data.get("record_version", 1),
            timestamps=data.get("timestamps", {}),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            metadata=data.get("metadata", {}),
        )
