"""Event Sequence Checker — Order consistency validation.

Validates event ordering and detects gaps in event sequences.
Ensures events are processed in the correct order for each order.

Pipeline:
    Sequence ID → Gap Detection → Replay Request → Recovery

Key features:
- Per-order sequence number tracking
- Gap detection with automatic recovery requests
- Out-of-order event handling
- Sequence window management
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class SequenceStatus(str, Enum):
    """Sequence check result status."""
    IN_ORDER = "in_order"
    OUT_OF_ORDER = "out_of_order"
    GAP_DETECTED = "gap_detected"
    DUPLICATE = "duplicate"
    STALE = "stale"


@dataclass
class SequenceResult:
    """Result of sequence validation."""
    order_id: str
    sequence_id: int
    status: SequenceStatus
    expected_next: int
    missing_sequences: list[int] = field(default_factory=list)
    message: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def needs_recovery(self) -> bool:
        """Whether recovery is needed due to gaps."""
        return self.status == SequenceStatus.GAP_DETECTED and len(self.missing_sequences) > 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "order_id": self.order_id,
            "sequence_id": self.sequence_id,
            "status": self.status.value,
            "expected_next": self.expected_next,
            "missing_sequences": self.missing_sequences,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
        }


class EventSequenceChecker:
    """Validates event ordering and detects sequence gaps.

    Each order maintains its own monotonic sequence counter. Events
    must arrive with increasing sequence IDs. Gaps trigger recovery.

    Usage::

        checker = EventSequenceChecker()
        result = checker.check(order_id, sequence_id)
        if result.needs_recovery:
            await recover_missing_events(order_id, result.missing_sequences)
    """

    def __init__(
        self,
        max_window_size: int = 1000,
        stale_threshold: int = 100,
    ) -> None:
        """Initialize sequence checker.

        Args:
            max_window_size: Maximum number of sequence IDs to track per order
            stale_threshold: Mark sequence as stale if gap exceeds this many
        """
        self._max_window_size = max_window_size
        self._stale_threshold = stale_threshold
        # order_id → next_expected_sequence
        self._sequences: dict[str, int] = defaultdict(lambda: 1)
        # order_id → set of received sequence IDs
        self._received: dict[str, set[int]] = defaultdict(set)
        # order_id → highest received sequence ID
        self._high_water: dict[str, int] = defaultdict(int)

    def check(self, order_id: str, sequence_id: int) -> SequenceResult:
        """Check the sequence of an incoming event.

        Args:
            order_id: Order identifier
            sequence_id: Sequence number of the event

        Returns:
            SequenceResult with ordering analysis
        """
        expected = self._sequences[order_id]

        # Initialize first event
        if sequence_id == 1 and expected == 1:
            self._advance(order_id, sequence_id)
            return SequenceResult(
                order_id=order_id,
                sequence_id=sequence_id,
                status=SequenceStatus.IN_ORDER,
                expected_next=expected + 1,
                message="Initial event — sequence started",
            )

        # Exact next expected
        if sequence_id == expected:
            self._advance(order_id, sequence_id)
            return SequenceResult(
                order_id=order_id,
                sequence_id=sequence_id,
                status=SequenceStatus.IN_ORDER,
                expected_next=expected + 1,
                message=f"Sequence {sequence_id} in order",
            )

        # Future sequence — gap detected
        if sequence_id > expected:
            missing = list(range(expected, sequence_id))
            self._received[order_id].add(sequence_id)
            self._high_water[order_id] = max(self._high_water[order_id], sequence_id)

            logger.warning(
                f"Sequence gap detected: order={order_id}, "
                f"expected={expected}, received={sequence_id}, "
                f"missing={missing}"
            )

            return SequenceResult(
                order_id=order_id,
                sequence_id=sequence_id,
                status=SequenceStatus.GAP_DETECTED,
                expected_next=expected,
                missing_sequences=missing,
                message=f"Gap detected: expected {expected}, got {sequence_id}, missing {len(missing)} events",
            )

        # Past sequence — out of order or duplicate
        if sequence_id in self._received[order_id]:
            logger.info(f"Duplicate sequence: order={order_id}, seq={sequence_id}")
            return SequenceResult(
                order_id=order_id,
                sequence_id=sequence_id,
                status=SequenceStatus.DUPLICATE,
                expected_next=expected,
                message=f"Duplicate sequence: {sequence_id}",
            )

        # Stale sequence
        if expected - sequence_id > self._stale_threshold:
            logger.warning(
                f"Stale sequence: order={order_id}, "
                f"seq={sequence_id}, expected={expected}"
            )
            return SequenceResult(
                order_id=order_id,
                sequence_id=sequence_id,
                status=SequenceStatus.STALE,
                expected_next=expected,
                message=f"Stale sequence {sequence_id} (expecting {expected})",
            )

        # Out of order (but within window)
        self._received[order_id].add(sequence_id)
        logger.info(
            f"Out-of-order event: order={order_id}, "
            f"seq={sequence_id}, expected={expected}"
        )
        return SequenceResult(
            order_id=order_id,
            sequence_id=sequence_id,
            status=SequenceStatus.OUT_OF_ORDER,
            expected_next=expected,
            message=f"Out-of-order sequence {sequence_id} (expecting {expected})",
        )

    async def acheck(
        self, order_id: str, sequence_id: int
    ) -> SequenceResult:
        """Async-compatible sequence check.

        Args:
            order_id: Order identifier
            sequence_id: Sequence number

        Returns:
            SequenceResult with ordering analysis
        """
        return self.check(order_id, sequence_id)

    def acknowledge(self, order_id: str, sequence_id: int) -> None:
        """Acknowledge receipt of a specific sequence (for gap filling).

        Args:
            order_id: Order identifier
            sequence_id: Acknowledged sequence number
        """
        self._advance(order_id, sequence_id)

    def _advance(self, order_id: str, sequence_id: int) -> None:
        """Advance the expected sequence for an order."""
        self._received[order_id].add(sequence_id)
        self._high_water[order_id] = max(self._high_water[order_id], sequence_id)

        # Find next expected by checking contiguous received range
        next_seq = sequence_id + 1
        while next_seq in self._received[order_id]:
            next_seq += 1
        self._sequences[order_id] = next_seq

        # Clean old entries
        self._prune_received(order_id)

    def _prune_received(self, order_id: str) -> None:
        """Remove old sequence entries to prevent unbounded growth."""
        received = self._received[order_id]
        expected = self._sequences[order_id]
        if len(received) > self._max_window_size:
            to_remove = {s for s in received if s < expected}
            received.difference_update(to_remove)

    def get_expected_next(self, order_id: str) -> int:
        """Get the next expected sequence ID for an order.

        Args:
            order_id: Order identifier

        Returns:
            Next expected sequence number
        """
        return self._sequences.get(order_id, 1)

    def get_missing_sequences(self, order_id: str) -> list[int]:
        """Get all missing sequence IDs for an order.

        Args:
            order_id: Order identifier

        Returns:
            List of missing sequence numbers
        """
        expected = self._sequences[order_id]
        high = self._high_water.get(order_id, 0)
        received = self._received.get(order_id, set())
        if high <= expected:
            return []
        return [s for s in range(expected, high) if s not in received]

    def reset(self, order_id: str) -> None:
        """Reset sequence tracking for an order.

        Args:
            order_id: Order identifier
        """
        self._sequences.pop(order_id, None)
        self._received.pop(order_id, None)
        self._high_water.pop(order_id, None)
        logger.debug(f"Sequence tracking reset for order {order_id}")

    def to_dict(self) -> dict[str, Any]:
        """Serialize checker state."""
        return {
            "tracked_orders": len(self._sequences),
            "max_window_size": self._max_window_size,
            "stale_threshold": self._stale_threshold,
            "sequences": {
                oid: {
                    "next_expected": self._sequences[oid],
                    "high_water": self._high_water.get(oid, 0),
                    "received_count": len(self._received.get(oid, set())),
                }
                for oid in self._sequences
            },
        }
