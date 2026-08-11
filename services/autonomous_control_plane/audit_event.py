"""
Audit Event — Structured audit event model.
"""

from __future__ import annotations

import uuid
import time
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class AuditEvent:
    """
    A single audit event recording a decision or action.
    """
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    event_type: str = ""
    actor: str = "autonomous"
    action: str = ""
    entity_type: str = ""
    entity_id: str = ""
    trace_id: str = ""
    decision_id: str = ""
    outcome: str = ""
    context_snapshot: Optional[dict] = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "actor": self.actor,
            "action": self.action,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "trace_id": self.trace_id,
            "decision_id": self.decision_id,
            "outcome": self.outcome,
            "metadata": self.metadata,
        }
