"""Event store domain layer (Commit 34 Part 1.1 / 1.2)."""

from services.event_store.domain.errors import (
    ConcurrencyConflictError,
    EventAlreadyExistsError,
    EventStoreError,
    InvalidEventVersionError,
)
from services.event_store.domain.event import StoredEvent
from services.event_store.domain.stream import (
    AppendRequest,
    EventStream,
    ensure_event_identity,
    validate_event_sequence,
)

__all__ = [
    "AppendRequest",
    "ConcurrencyConflictError",
    "EventAlreadyExistsError",
    "EventStoreError",
    "EventStream",
    "InvalidEventVersionError",
    "StoredEvent",
    "ensure_event_identity",
    "validate_event_sequence",
]
