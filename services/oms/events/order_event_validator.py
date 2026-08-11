"""OrderEventValidator — validates events before appending to the store."""
from __future__ import annotations

from typing import List

from .order_event import OrderEvent
from .order_event_type import OrderEventType
from .order_event_errors import (
    EventValidationError,
    EventSequenceGapError,
    EventHashChainError,
    DuplicateEventError,
    EventCollisionError,
)
from .order_event_sequence import OrderEventSequence


class OrderEventValidator:
    """Validates order events for integrity, sequence, and hash chain."""

    def __init__(self) -> None:
        pass

    # ── Single event validation ───────────────────

    @staticmethod
    def validate_event(event: OrderEvent) -> None:
        """Validate a single event's fields.

        Raises EventValidationError on failure.
        """
        if not event.order_id:
            raise EventValidationError("", "order_id", "Missing order_id")
        if not event.event_id:
            raise EventValidationError(
                event.order_id, "event_id", "Missing event_id",
            )
        if event.sequence < 1:
            raise EventValidationError(
                event.order_id, "sequence",
                f"Sequence must be >= 1, got {event.sequence}",
            )
        if not event.lineage_id:
            raise EventValidationError(
                event.order_id, "lineage_id", "Missing lineage_id",
            )
        if not event.is_sealed:
            raise EventValidationError(
                event.order_id, "event_hash", "Event not sealed",
            )
        if not event.verify_hash():
            raise EventValidationError(
                event.order_id, "event_hash", "Hash verification failed",
            )

    # ── Sequence validation ───────────────────────

    @staticmethod
    def validate_sequence(events: List[OrderEvent]) -> None:
        """Validate that events form a gap-free sequence starting at 1."""
        if not events:
            return
        sorted_events = sorted(events, key=lambda e: e.sequence)
        expected = 1
        for evt in sorted_events:
            if evt.sequence != expected:
                raise EventSequenceGapError(
                    evt.order_id, expected=expected, actual=evt.sequence,
                )
            expected += 1

    @staticmethod
    def check_for_gaps(events: List[OrderEvent]) -> List[int]:
        """Return list of missing sequence numbers."""
        if not events:
            return []
        sequences = [e.sequence for e in events]
        return OrderEventSequence.find_gaps(sequences)

    # ── Hash chain validation ─────────────────────

    @staticmethod
    def validate_hash_chain(events: List[OrderEvent]) -> None:
        """Validate the hash chain of an event stream.

        Checks:
        1. Each event's previous_event_hash matches the prior event's hash.
        2. Each event's stored hash matches its computed hash.
        """
        if not events:
            return
        sorted_events = sorted(events, key=lambda e: e.sequence)
        prev_hash = ""
        for evt in sorted_events:
            # Check hash integrity
            if not evt.verify_hash():
                raise EventHashChainError(
                    evt.order_id, evt.event_id,
                    expected_hash=evt.compute_hash(),
                    actual_hash=evt.event_hash,
                )
            # Check chain linkage
            if evt.previous_event_hash != prev_hash:
                raise EventHashChainError(
                    evt.order_id, evt.event_id,
                    expected_hash=prev_hash,
                    actual_hash=evt.previous_event_hash,
                )
            prev_hash = evt.event_hash

    # ── Duplicate detection ───────────────────────

    @staticmethod
    def check_duplicate(new_event: OrderEvent,
                        existing_events: List[OrderEvent]) -> bool:
        """Check if new_event duplicates an existing event.

        Returns:
            True if this is a duplicate (caller should handle).

        Raises:
            EventCollisionError: if the same event_id has different content.
            DuplicateEventError: if it's a true duplicate.
        """
        for existing in existing_events:
            if existing.event_id == new_event.event_id:
                if existing.fingerprint() == new_event.fingerprint():
                    raise DuplicateEventError(
                        new_event.order_id,
                        new_event.event_id,
                        new_event.sequence,
                        idempotent=True,
                    )
                else:
                    raise EventCollisionError(
                        new_event.order_id,
                        new_event.event_id,
                        new_event.sequence,
                    )
            if existing.sequence == new_event.sequence:
                if existing.fingerprint() == new_event.fingerprint():
                    raise DuplicateEventError(
                        new_event.order_id,
                        new_event.event_id,
                        new_event.sequence,
                        idempotent=True,
                    )
                else:
                    raise EventCollisionError(
                        new_event.order_id,
                        new_event.event_id,
                        new_event.sequence,
                    )
        return False

    # ── Full stream validation ────────────────────

    @staticmethod
    def validate_stream(events: List[OrderEvent]) -> None:
        """Validate an entire event stream.

        Checks sequence, hash chain, and individual event integrity.
        """
        for evt in events:
            OrderEventValidator.validate_event(evt)
        OrderEventValidator.validate_sequence(events)
        OrderEventValidator.validate_hash_chain(events)
