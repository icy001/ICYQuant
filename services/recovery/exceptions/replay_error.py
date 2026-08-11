"""Replay exceptions — errors during event replay."""

from typing import Optional

from .recovery_error import RecoveryError


class ReplayError(RecoveryError):
    """Base exception for replay failures."""

    def __init__(self, message: str = "Replay error"):
        super().__init__(message)


class SequenceGapError(ReplayError):
    """Event sequence has a gap — cannot replay safely."""

    def __init__(
        self,
        expected_seq: int,
        actual_seq: int,
        aggregate_id: Optional[str] = None,
    ):
        self.expected_seq = expected_seq
        self.actual_seq = actual_seq
        self.aggregate_id = aggregate_id
        parts = [f"Event sequence gap: expected {expected_seq}, got {actual_seq}"]
        if aggregate_id:
            parts.append(f"(aggregate={aggregate_id})")
        super().__init__(" ".join(parts))


class EventValidationError(ReplayError):
    """An event loaded for replay failed validation."""

    def __init__(self, event_id: str, reason: str):
        self.event_id = event_id
        self.reason = reason
        super().__init__(f"Event validation failed for {event_id}: {reason}")


class ReplayIdempotencyError(ReplayError):
    """The event was already applied — would cause duplicate state change."""

    def __init__(self, event_id: str, existing_entry_id: str):
        self.event_id = event_id
        self.existing_entry_id = existing_entry_id
        super().__init__(
            f"Event {event_id} already applied (existing entry: {existing_entry_id})"
        )
