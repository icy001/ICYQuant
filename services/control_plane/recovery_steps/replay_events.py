"""
REPLAY_EVENTS step.

#10/#15/#16 — events are replayed from a cursor and validated for:

    event_count   (expected vs actual)
    sequence      (no gaps — a missing event may decide the final position)
    checksum      (expected checksum equals actual checksum)

A replay must never run 10M events and then fail at the end: the orchestrator
persists the cursor as a checkpoint after every successful step, so a retry
continues from ``event_cursor + 1`` instead of restarting.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from ..recovery.recovery_checkpoint import compute_checksum
from ..recovery.recovery_context import RecoveryContext
from ..recovery.recovery_step import RecoveryStep, StepOutcome, StepType
from . import StepExecutor, register_step_executor

EventStore = Callable[[int], List[Dict[str, Any]]]


def _find_gap(events: List[Dict[str, Any]], from_cursor: int = 0) -> Optional[int]:
    """Return the first missing sequence number, or None when contiguous."""
    if not events:
        return None
    first_seq = int(events[0].get("seq", 0))
    expected_start = from_cursor + 1 if from_cursor else None
    if expected_start is not None and first_seq != expected_start:
        return expected_start
    prev = first_seq
    for event in events[1:]:
        seq = int(event.get("seq", 0))
        if seq != prev + 1:
            return prev + 1
        prev = seq
    return None


@register_step_executor
class ReplayEventsExecutor(StepExecutor):
    """Replay and validate the event stream."""

    step_type = StepType.REPLAY_EVENTS

    def __init__(self, event_store: Optional[EventStore] = None) -> None:
        # event_store: callable(from_cursor) -> list of event dicts with "seq"
        self.event_store = event_store

    def execute(self, step: RecoveryStep, context: RecoveryContext) -> StepOutcome:
        from_cursor = int(step.input.get("event_cursor", 0) or 0)

        if self.event_store is not None:
            events = list(self.event_store(from_cursor))
        else:
            events = list(step.input.get("events", []) or [])
        events = sorted(events, key=lambda e: int(e.get("seq", 0)))

        gap = _find_gap(events, from_cursor)
        if gap is not None:
            return StepOutcome(
                success=False,
                output={"event_cursor": from_cursor, "replayed_events": 0},
                error=f"EVENT_GAP: missing event {gap}",
                error_code="EVENT_GAP",
            )

        expected_count = step.input.get("expected_events")
        if expected_count is not None and int(expected_count) != len(events):
            return StepOutcome(
                success=False,
                output={"event_cursor": from_cursor, "replayed_events": len(events)},
                error=f"expected {expected_count} events, replayed {len(events)}",
                error_code="EVENT_COUNT_MISMATCH",
            )

        checksum = compute_checksum({"events": events})
        expected_checksum = step.input.get("expected_checksum")
        if expected_checksum and expected_checksum != checksum:
            return StepOutcome(
                success=False,
                output={"event_cursor": from_cursor, "replayed_events": len(events)},
                error="CHECKSUM_MISMATCH: expected != actual",
                error_code="CHECKSUM_MISMATCH",
            )

        next_cursor = from_cursor + len(events) if events else from_cursor
        return StepOutcome(
            success=True,
            output={
                "event_cursor": next_cursor,
                "replayed_events": len(events),
                "checksum": checksum,
                "complete": True,
            },
        )
