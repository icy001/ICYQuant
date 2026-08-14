"""Event store domain errors (Commit 34 Part 1.1 #5)."""

from __future__ import annotations


class EventStoreError(Exception):
    """Base error for the durable event store."""


class EventAlreadyExistsError(EventStoreError):
    """Raised when appending an ``event_id`` that is already stored (#5)."""


class InvalidEventVersionError(EventStoreError):
    """Raised when a stream's version continuity is broken (#5).

    A stream may only grow one version at a time: v1 -> v2 -> v3 is legal,
    v1 -> v3 and v2 -> v2 are rejected.
    """


class ConcurrencyConflictError(EventStoreError):
    """Raised when an append targets a stale expected version (Part 1.2 #4).

    Two commands raced on the same aggregate: one committed, the other must
    re-read the stream and re-apply.  The system never silently overwrites a
    committed result.
    """

    def __init__(
        self,
        aggregate_id: str,
        expected_version: int,
        actual_version: int,
    ) -> None:
        self.aggregate_id = aggregate_id
        self.expected_version = expected_version
        self.actual_version = actual_version

        super().__init__(
            f"aggregate={aggregate_id} "
            f"expected_version={expected_version} "
            f"actual_version={actual_version}"
        )
