"""Audit Event — the indivisible unit of the decision audit chain.

Each AuditEvent captures a point-in-time fact about the control
lineage.  Events are append-only and form a hash-linked chain.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


class ActorType(Enum):
    """Who (or what) produced this audit event."""

    SYSTEM = auto()
    SERVICE = auto()
    USER = auto()
    STRATEGY = auto()
    RISK_ENGINE = auto()
    GOVERNANCE_ENGINE = auto()
    AUTHORITY_ENGINE = auto()
    APPROVAL_ENGINE = auto()
    OMS = auto()
    EXECUTION_ENGINE = auto()

    @property
    def label(self) -> str:
        _labels: dict[ActorType, str] = {
            ActorType.SYSTEM: "System",
            ActorType.SERVICE: "Service",
            ActorType.USER: "User",
            ActorType.STRATEGY: "Strategy",
            ActorType.RISK_ENGINE: "Risk Engine",
            ActorType.GOVERNANCE_ENGINE: "Governance Engine",
            ActorType.AUTHORITY_ENGINE: "Authority Engine",
            ActorType.APPROVAL_ENGINE: "Approval Engine",
            ActorType.OMS: "OMS",
            ActorType.EXECUTION_ENGINE: "Execution Engine",
        }
        return _labels.get(self, self.name)


class EventType(Enum):
    """Types of auditable events in the control lineage."""

    DECISION_CREATED = auto()
    SIGNAL_RECEIVED = auto()
    RISK_EVALUATED = auto()
    GOVERNANCE_EVALUATED = auto()
    AUTHORITY_CHECKED = auto()
    APPROVAL_GRANTED = auto()
    APPROVAL_DENIED = auto()
    APPROVAL_REVOKED = auto()
    ORDER_INTENT_CREATED = auto()
    ORDER_ADMITTED = auto()
    ORDER_REJECTED = auto()
    CERTIFICATE_ISSUED = auto()
    CERTIFICATE_REVOKED = auto()
    CERTIFICATE_EXPIRED = auto()
    ORDER_CREATED = auto()
    ORDER_SUBMITTED = auto()
    ORDER_FILLED = auto()
    ORDER_CANCELLED = auto()
    EXECUTION_STARTED = auto()
    EXECUTION_COMPLETED = auto()
    TRADE_RECORDED = auto()
    POSITION_UPDATED = auto()
    LEDGER_EVENT_RECORDED = auto()

    @property
    def label(self) -> str:
        _labels: dict[EventType, str] = {
            EventType.DECISION_CREATED: "Decision Created",
            EventType.SIGNAL_RECEIVED: "Signal Received",
            EventType.RISK_EVALUATED: "Risk Evaluated",
            EventType.GOVERNANCE_EVALUATED: "Governance Evaluated",
            EventType.AUTHORITY_CHECKED: "Authority Checked",
            EventType.APPROVAL_GRANTED: "Approval Granted",
            EventType.APPROVAL_DENIED: "Approval Denied",
            EventType.APPROVAL_REVOKED: "Approval Revoked",
            EventType.ORDER_INTENT_CREATED: "Order Intent Created",
            EventType.ORDER_ADMITTED: "Order Admitted",
            EventType.ORDER_REJECTED: "Order Rejected",
            EventType.CERTIFICATE_ISSUED: "Certificate Issued",
            EventType.CERTIFICATE_REVOKED: "Certificate Revoked",
            EventType.CERTIFICATE_EXPIRED: "Certificate Expired",
            EventType.ORDER_CREATED: "Order Created",
            EventType.ORDER_SUBMITTED: "Order Submitted",
            EventType.ORDER_FILLED: "Order Filled",
            EventType.ORDER_CANCELLED: "Order Cancelled",
            EventType.EXECUTION_STARTED: "Execution Started",
            EventType.EXECUTION_COMPLETED: "Execution Completed",
            EventType.TRADE_RECORDED: "Trade Recorded",
            EventType.POSITION_UPDATED: "Position Updated",
            EventType.LEDGER_EVENT_RECORDED: "Ledger Event Recorded",
        }
        return _labels.get(self, self.name)


def compute_event_hash(event_id: str, event_type: str, lineage_id: str,
                       timestamp: float, actor: str, actor_id: str,
                       payload: dict[str, Any],
                       previous_event_hash: str = "",
                       ) -> str:
    """Compute a deterministic SHA-256 hash over audit event fields."""
    import hashlib
    import json

    material: dict[str, Any] = {
        "event_id": event_id,
        "event_type": event_type,
        "lineage_id": lineage_id,
        "timestamp": timestamp,
        "actor": actor,
        "actor_id": actor_id,
        "payload": payload,
        "previous_event_hash": previous_event_hash,
    }
    # canonical JSON for reproducibility
    serialized = json.dumps(material, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


@dataclass
class AuditEvent:
    """A single auditable event in the control lineage audit chain.

    AuditEvents are append-only.  They form a hash-linked chain via
    `previous_event_hash` → `event_hash`.
    """

    event_id: str = field(
        default_factory=lambda: (
            f"AEVT-{__import__('uuid').uuid4().hex[:12].upper()}"
        ),
    )
    event_type: EventType = EventType.DECISION_CREATED
    lineage_id: str = ""
    timestamp: float = field(
        default_factory=lambda: __import__("time").time(),
    )

    # ── Actor ─────────────────────────────────────────────────────
    actor_type: ActorType = ActorType.SYSTEM
    actor_id: str = ""

    # ── Payload ───────────────────────────────────────────────────
    payload: dict[str, Any] = field(default_factory=dict)

    # ── Chain linkage ─────────────────────────────────────────────
    previous_event_hash: str = ""
    event_hash: str = ""
    sequence_number: int = 0

    # ── Computational ─────────────────────────────────────────────

    def compute_hash(self, previous_hash: str | None = None) -> str:
        """Compute and return this event's hash, optionally chaining."""
        prev = (
            previous_hash
            if previous_hash is not None
            else self.previous_event_hash
        )
        return compute_event_hash(
            event_id=self.event_id,
            event_type=self.event_type.name,
            lineage_id=self.lineage_id,
            timestamp=self.timestamp,
            actor=self.actor_type.name,
            actor_id=self.actor_id,
            payload=self.payload,
            previous_event_hash=prev,
        )

    def seal(self, previous_hash: str = "",
             sequence_number: int = 0) -> "AuditEvent":
        """Finalize this event by computing and embedding its hash."""
        self.previous_event_hash = previous_hash
        self.sequence_number = sequence_number
        self.event_hash = self.compute_hash(previous_hash)
        return self

    # ── Properties ────────────────────────────────────────────────

    @property
    def is_control_event(self) -> bool:
        return self.event_type in {
            EventType.RISK_EVALUATED,
            EventType.GOVERNANCE_EVALUATED,
            EventType.AUTHORITY_CHECKED,
            EventType.APPROVAL_GRANTED,
            EventType.APPROVAL_DENIED,
        }

    @property
    def is_execution_event(self) -> bool:
        return self.event_type in {
            EventType.ORDER_FILLED,
            EventType.EXECUTION_COMPLETED,
            EventType.TRADE_RECORDED,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.name,
            "lineage_id": self.lineage_id,
            "timestamp": self.timestamp,
            "actor_type": self.actor_type.name,
            "actor_id": self.actor_id,
            "payload": dict(self.payload),
            "previous_event_hash": self.previous_event_hash,
            "event_hash": self.event_hash,
            "sequence_number": self.sequence_number,
        }

    @classmethod
    def create(cls, event_type: EventType, lineage_id: str,
               actor_type: ActorType = ActorType.SYSTEM,
               actor_id: str = "",
               payload: dict[str, Any] | None = None,
               ) -> "AuditEvent":
        """Factory for an unsealed audit event."""
        import time as _t
        return cls(
            event_type=event_type,
            lineage_id=lineage_id,
            timestamp=_t.time(),
            actor_type=actor_type,
            actor_id=actor_id,
            payload=payload or {},
        )
