"""Event stream domain model (Commit 34 Part 1.2 #2 / #3 / #8 / #9).

Part 1.2 promotes the stream from a passive list of events into a first-class
domain concept:

* ``EventStream`` - an aggregate's versioned history;
* ``AppendRequest`` - an atomic multi-event append with an expected version;
* ``validate_event_sequence`` - contiguous version validation for a batch;
* ``ensure_event_identity`` - idempotency guard: the same ``event_id`` must
  always carry the same fact (payload).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from services.event_store.domain.errors import EventAlreadyExistsError
from services.event_store.domain.event import StoredEvent


@dataclass(frozen=True)
class EventStream:
    """An aggregate stream header, describing where the stream stands now (#2).

    .. code-block:: text

        aggregate_id      = ORDER-001
        aggregate_type    = Order
        current_version   = 7
        next_version      = 8
    """

    aggregate_id: str
    aggregate_type: str
    current_version: int

    @property
    def next_version(self) -> int:
        return self.current_version + 1

    def __post_init__(self) -> None:
        if not self.aggregate_id:
            raise ValueError("aggregate_id is required")
        if not self.aggregate_type:
            raise ValueError("aggregate_type is required")
        if self.current_version < 0:
            raise ValueError("current_version must be non-negative")


@dataclass(frozen=True)
class AppendRequest:
    """An atomic append of a batch of events to one aggregate stream (#3).

    The store only writes when ``current_version == expected_version``.
    """

    aggregate_id: str
    expected_version: int
    events: Tuple[StoredEvent, ...]


def validate_event_sequence(
    expected_version: int,
    events: Tuple[StoredEvent, ...],
) -> None:
    """Validate that a batch continues the stream without gaps (#8).

    With ``expected_version = 7`` the batch must be v8, v9, v10 - never
    v8 -> v10 (gap) nor v9 -> v10 (overlap).
    """

    version = expected_version

    for event in events:
        version += 1

        if event.aggregate_version != version:
            raise ValueError("invalid event sequence")


def ensure_event_identity(
    existing: Optional[StoredEvent],
    incoming: StoredEvent,
) -> None:
    """Idempotency guard for event persistence (#9).

    * no existing event -> nothing to check;
    * same ``event_id`` with the same payload -> an idempotent retry;
    * same ``event_id`` with a different payload -> rejected.
    """

    if existing is None:
        return

    if existing.payload != incoming.payload:
        raise EventAlreadyExistsError(incoming.event_id)
