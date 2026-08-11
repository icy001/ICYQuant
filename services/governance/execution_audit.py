"""
Execution Audit — specialized audit for order execution lifecycle.

Records the complete execution path:
  ORDER_CREATED → ORDER_SUBMITTED → EXECUTION_STARTED
  → EXECUTION_COMPLETED / FAILED → TRADE → POSITION
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional

from .audit_event_type import AuditEventType
from .audit_actor import AuditActor, ActorType
from .audit_action import AuditAction
from .audit_outcome import AuditOutcome
from .audit_hash import AuditHash


class ExecutionStatus(Enum):
    """Execution lifecycle statuses."""

    ORDER_CREATED = auto()
    ORDER_VALIDATED = auto()
    ORDER_APPROVED = auto()
    ORDER_REJECTED = auto()
    ORDER_SUBMITTED = auto()
    ORDER_CANCELLED = auto()
    EXECUTION_STARTED = auto()
    EXECUTION_PARTIAL = auto()
    EXECUTION_COMPLETED = auto()
    EXECUTION_FAILED = auto()
    TRADE_CONFIRMED = auto()
    POSITION_UPDATED = auto()


@dataclass
class ExecutionAudit:
    """Full audit trail of an order from creation to position update."""

    audit_id: str
    correlation_id: str = ""
    decision_id: str = ""

    # Order details
    order_id: str = ""
    instrument: str = ""
    side: str = ""
    quantity: float = 0.0
    price: float = 0.0
    amount: float = 0.0
    order_type: str = ""

    # Execution details
    execution_id: str = ""
    trade_id: str = ""
    filled_quantity: float = 0.0
    avg_price: float = 0.0
    venue: str = ""

    # Status tracking
    status: ExecutionStatus = ExecutionStatus.ORDER_CREATED
    status_history: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    # Certification
    certificate_id: str = ""
    certificate_hash: str = ""

    # Integrity
    audit_hash: str = ""
    actor: Optional[AuditActor] = None

    timestamps: Dict[str, float] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.audit_id:
            self.audit_id = f"EXAUD-{uuid.uuid4().hex[:12].upper()}"
        if self.status.name not in self.timestamps:
            self.timestamps[self.status.name] = time.time()

    def record_transition(
        self, new_status: ExecutionStatus, detail: str = ""
    ) -> None:
        """Record a status change."""
        old = self.status
        self.status = new_status
        self.timestamps[new_status.name] = time.time()
        self.status_history.append({
            "from": old.name,
            "to": new_status.name,
            "detail": detail,
            "timestamp": time.time(),
        })

    def add_error(self, error: str) -> None:
        self.errors.append(error)
        self.record_transition(ExecutionStatus.EXECUTION_FAILED, error)

    def compute_hash(self) -> str:
        data = {
            "audit_id": self.audit_id,
            "decision_id": self.decision_id,
            "order_id": self.order_id,
            "execution_id": self.execution_id,
            "trade_id": self.trade_id,
            "instrument": self.instrument,
            "side": self.side,
            "quantity": self.quantity,
            "amount": self.amount,
            "status": self.status.name,
            "created_at": self.created_at,
        }
        self.audit_hash = AuditHash.compute_snapshot_hash(data)
        return self.audit_hash

    def to_dict(self) -> Dict[str, Any]:
        return {
            "audit_id": self.audit_id,
            "correlation_id": self.correlation_id,
            "decision_id": self.decision_id,
            "order_id": self.order_id,
            "instrument": self.instrument,
            "side": self.side,
            "quantity": self.quantity,
            "price": self.price,
            "amount": self.amount,
            "order_type": self.order_type,
            "execution_id": self.execution_id,
            "trade_id": self.trade_id,
            "filled_quantity": self.filled_quantity,
            "avg_price": self.avg_price,
            "venue": self.venue,
            "status": self.status.name,
            "status_history": self.status_history,
            "errors": self.errors,
            "certificate_id": self.certificate_id,
            "certificate_hash": self.certificate_hash,
            "audit_hash": self.audit_hash,
            "actor": self.actor.to_dict() if self.actor else None,
            "timestamps": self.timestamps,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutionAudit":
        status = data.get("status", "ORDER_CREATED")
        if isinstance(status, str):
            status = ExecutionStatus[status]

        actor = AuditActor.from_dict(data["actor"]) if data.get("actor") else None

        return cls(
            audit_id=data.get("audit_id", ""),
            correlation_id=data.get("correlation_id", ""),
            decision_id=data.get("decision_id", ""),
            order_id=data.get("order_id", ""),
            instrument=data.get("instrument", ""),
            side=data.get("side", ""),
            quantity=data.get("quantity", 0.0),
            price=data.get("price", 0.0),
            amount=data.get("amount", 0.0),
            order_type=data.get("order_type", ""),
            execution_id=data.get("execution_id", ""),
            trade_id=data.get("trade_id", ""),
            filled_quantity=data.get("filled_quantity", 0.0),
            avg_price=data.get("avg_price", 0.0),
            venue=data.get("venue", ""),
            status=status,
            status_history=data.get("status_history", []),
            errors=data.get("errors", []),
            certificate_id=data.get("certificate_id", ""),
            certificate_hash=data.get("certificate_hash", ""),
            audit_hash=data.get("audit_hash", ""),
            actor=actor,
            timestamps=data.get("timestamps", {}),
            created_at=data.get("created_at", time.time()),
            metadata=data.get("metadata", {}),
        )
