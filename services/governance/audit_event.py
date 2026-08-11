"""
Audit Event — the core immutable audit event record for the governance system.

Each AuditEvent is:
  - Immutable after creation
  - Hash-chained to the previous event
  - Carries full actor, action, outcome, and context attribution
  - Can be serialized for persistence
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .audit_event_type import AuditEventType
from .audit_actor import AuditActor
from .audit_action import AuditAction
from .audit_outcome import AuditOutcome
from .audit_context import AuditContext


@dataclass
class AuditEvent:
    """Immutable governance audit event with hash chaining.

    Principles:
      1. Immutable after creation — properties are read-only post-init
      2. Hash-chained — previous_hash links to the prior event
      3. Fully attributed — actor, action, outcome, context all present
      4. Traceable — correlation_id + causation_id for full lineage
    """

    event_id: str

    # What happened
    event_type: AuditEventType
    entity_type: str  # "DECISION", "POLICY", "AUTHORITY", "APPROVAL", "ORDER", etc.
    entity_id: str    # The specific entity this event is about

    # Who did it
    actor: AuditActor

    # What action
    action: AuditAction

    # What was the result
    outcome: AuditOutcome = AuditOutcome.SUCCESS

    # Why
    reason: str = ""

    # Hash chain
    event_hash: str = ""
    previous_hash: str = ""

    # Correlation / Causation for lineage
    correlation_id: str = ""
    causation_id: str = ""

    # Rich context
    context: AuditContext = field(default_factory=AuditContext)

    # Extensibility
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Timing
    timestamp: float = field(default_factory=time.time)
    created_at: float = field(default_factory=time.time)

    # ── Immutability ──

    _frozen: bool = field(default=False, repr=False)

    def __post_init__(self):
        if not self.event_id:
            self.event_id = f"AEVT-{uuid.uuid4().hex[:12].upper()}"
        self._frozen = True

    def __setattr__(self, name, value):
        if getattr(self, "_frozen", False):
            raise AttributeError(
                f"AuditEvent is immutable after creation. Cannot set '{name}'."
            )
        super().__setattr__(name, value)

    # ── Serialization ──

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.name,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "actor": self.actor.to_dict(),
            "action": self.action.name,
            "outcome": self.outcome.name,
            "reason": self.reason,
            "event_hash": self.event_hash,
            "previous_hash": self.previous_hash,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "context": self.context.to_dict(),
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuditEvent":
        event_type = data.get("event_type", "SYSTEM_EVENT")
        if isinstance(event_type, str):
            event_type = AuditEventType[event_type]

        action = data.get("action", "CREATE")
        if isinstance(action, str):
            action = AuditAction[action]

        outcome = data.get("outcome", "SUCCESS")
        if isinstance(outcome, str):
            outcome = AuditOutcome[outcome]

        actor_data = data.get("actor", {})
        actor = AuditActor.from_dict(actor_data) if isinstance(actor_data, dict) else actor_data

        context_data = data.get("context", {})
        context = AuditContext.from_dict(context_data) if isinstance(context_data, dict) else context_data

        return cls(
            event_id=data.get("event_id", ""),
            event_type=event_type,
            entity_type=data.get("entity_type", ""),
            entity_id=data.get("entity_id", ""),
            actor=actor,
            action=action,
            outcome=outcome,
            reason=data.get("reason", ""),
            event_hash=data.get("event_hash", ""),
            previous_hash=data.get("previous_hash", ""),
            correlation_id=data.get("correlation_id", ""),
            causation_id=data.get("causation_id", ""),
            context=context,
            metadata=data.get("metadata", {}),
            timestamp=data.get("timestamp", time.time()),
            created_at=data.get("created_at", time.time()),
        )

    # ── Properties ──

    @property
    def is_critical(self) -> bool:
        return self.event_type.is_critical

    @property
    def is_terminal(self) -> bool:
        return self.event_type.is_terminal

    @property
    def event_summary(self) -> str:
        """Human-readable summary of this audit event."""
        return (
            f"[{self.event_type.name}] {self.actor.display_name} "
            f"{self.action.name} {self.entity_type}:{self.entity_id} "
            f"→ {self.outcome.name}"
        )

    def __repr__(self) -> str:
        return f"AuditEvent({self.event_id}, {self.event_type.name})"
