"""Outbox message model (Commit 33 Part 1.5 #2 / #9)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional


class OutboxStatus(str, Enum):
    """Lifecycle of an outbox message."""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class OutboxMessage:
    """One event staged for reliable delivery.

    ``message_id`` and ``event_id`` are both globally unique; for events staged
    by :class:`~services.order.engine.outbox.service.OutboxService` they are the
    same value, so the outbox/event idempotency relation is natural (#4).
    ``aggregate_id`` is the order id and ``aggregate_version`` the per-aggregate
    event version - v1 -> v2 -> v3, never v1 -> v3 -> v2 (#9).
    """

    message_id: str
    aggregate_id: str
    aggregate_type: str
    aggregate_version: int

    event_id: str
    event_type: str

    correlation_id: str
    causation_id: Optional[str]

    payload: Dict[str, Any]

    occurred_at: datetime
    created_at: datetime

    status: OutboxStatus = OutboxStatus.PENDING
    retry_count: int = 0
    last_error: Optional[str] = None
    published_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if not self.message_id:
            raise ValueError("message_id is required")
        if not self.event_id:
            raise ValueError("event_id is required")
        if not self.aggregate_type:
            raise ValueError("aggregate_type is required")
        if self.aggregate_version < 1:
            raise ValueError("aggregate_version must be a positive integer")
        if self.retry_count < 0:
            raise ValueError("retry_count must be non-negative")


def validate_version(previous_version: int, current_version: int) -> None:
    """Enforce strict per-aggregate version continuity (#9).

    The next event for an aggregate must carry exactly ``previous_version + 1``
    - a jump (v1 -> v3) or a repeat (v2 -> v2) is an invalid aggregate event
    version.
    """
    if current_version != previous_version + 1:
        raise ValueError(
            f"invalid aggregate event version: expected {previous_version + 1}, "
            f"got {current_version}"
        )
