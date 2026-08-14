"""Outbox error types (Commit 33 Part 1.5 #8)."""

from __future__ import annotations


class OutboxError(RuntimeError):
    """Base error for the transactional outbox layer."""


class DuplicateEventError(OutboxError):
    """Raised when an ``event_id`` is appended to the outbox twice (#8).

    A repeated append must fail loudly - never produce ``EVT-001-copy``.
    """


class OutboxMessageNotFoundError(OutboxError):
    """Raised when a ``message_id`` does not exist in the outbox."""


class OutboxPersistenceError(OutboxError):
    """Raised when the outbox cannot be written (fail-closed, #10)."""


class OutboxPublishError(OutboxError):
    """Raised when the event bus cannot be reached (fail-closed, #11)."""
