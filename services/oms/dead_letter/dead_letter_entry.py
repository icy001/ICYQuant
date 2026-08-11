"""DeadLetterEntry — a message that could not be processed."""
from __future__ import annotations

import time
import hashlib
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, Optional


class DeadLetterStatus(Enum):
    """Status of a dead-letter entry."""

    OPEN = auto()
    RETRYING = auto()
    RESOLVED = auto()
    ESCALATED = auto()
    IGNORED = auto()

    @property
    def label(self) -> str:
        return self.name.title()

    @property
    def is_terminal(self) -> bool:
        return self in (DeadLetterStatus.RESOLVED, DeadLetterStatus.IGNORED)


@dataclass
class DeadLetterEntry:
    """A message that could not be processed automatically.

    Dead-letter entries are NOT discarded — they are retained until
    explicitly resolved. Every entry has a full audit trail.
    """

    dead_letter_id: str = field(
        default_factory=lambda: f"DLQ-{__import__('uuid').uuid4().hex[:8].upper()}"
    )
    message_id: str = ""
    order_id: str = ""

    message_type: str = ""  # EXECUTION_REPORT, ACK, CANCEL_ACK, etc.
    payload_hash: str = ""

    failure_code: str = ""
    failure_reason: str = ""

    payload: Dict[str, Any] = field(default_factory=dict)

    status: DeadLetterStatus = DeadLetterStatus.OPEN
    attempt_count: int = 0

    created_at: float = field(default_factory=lambda: __import__("time").time())
    last_attempt_at: float = 0.0
    resolved_at: float = 0.0
    resolved_by: str = ""
    resolution_reason: str = ""

    @classmethod
    def create(cls, message_id: str, order_id: str,
               message_type: str,
               failure_code: str,
               failure_reason: str,
               payload: Optional[Dict[str, Any]] = None) -> "DeadLetterEntry":
        import json
        payload = payload or {}
        content = json.dumps(payload, sort_keys=True, default=str)
        return cls(
            message_id=message_id,
            order_id=order_id,
            message_type=message_type,
            failure_code=failure_code,
            failure_reason=failure_reason,
            payload=payload,
            payload_hash=hashlib.sha256(content.encode()).hexdigest(),
        )

    def record_attempt(self) -> None:
        self.attempt_count += 1
        self.last_attempt_at = time.time()
        if self.status == DeadLetterStatus.OPEN:
            self.status = DeadLetterStatus.RETRYING

    def resolve(self, resolved_by: str, reason: str = "") -> None:
        self.status = DeadLetterStatus.RESOLVED
        self.resolved_at = time.time()
        self.resolved_by = resolved_by
        self.resolution_reason = reason

    def escalate(self) -> None:
        self.status = DeadLetterStatus.ESCALATED
        self.last_attempt_at = time.time()

    def ignore(self, actor: str, reason: str) -> None:
        """Mark as ignored — requires actor and reason."""
        self.status = DeadLetterStatus.IGNORED
        self.resolved_at = time.time()
        self.resolved_by = actor
        self.resolution_reason = reason

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dead_letter_id": self.dead_letter_id,
            "message_id": self.message_id,
            "order_id": self.order_id,
            "message_type": self.message_type,
            "payload_hash": self.payload_hash,
            "failure_code": self.failure_code,
            "failure_reason": self.failure_reason,
            "status": self.status.name,
            "attempt_count": self.attempt_count,
            "created_at": self.created_at,
            "last_attempt_at": self.last_attempt_at,
            "resolved_at": self.resolved_at,
            "resolved_by": self.resolved_by,
            "resolution_reason": self.resolution_reason,
        }
