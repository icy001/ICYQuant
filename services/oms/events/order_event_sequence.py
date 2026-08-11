"""OrderEventSequence — monotonic sequence tracking for event streams."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .order_event_errors import EventSequenceGapError


@dataclass
class OrderEventSequence:
    """Tracks the sequence of events for a single order.

    Sequence numbers are 1-based and strictly monotonic.
    Gaps are not allowed — a missing sequence number indicates
    a lost event and must block trusted reconstruction.
    """

    order_id: str = ""
    next_sequence: int = 1
    last_sequence: int = 0

    @classmethod
    def for_order(cls, order_id: str) -> "OrderEventSequence":
        return cls(order_id=order_id)

    def allocate(self) -> int:
        """Allocate and return the next sequence number."""
        seq = self.next_sequence
        self.next_sequence += 1
        self.last_sequence = seq
        return seq

    def expect_next(self, sequence: int) -> None:
        """Validate that `sequence` is the expected next sequence.

        Raises EventSequenceGapError if there's a gap.
        """
        if sequence != self.next_sequence:
            raise EventSequenceGapError(
                self.order_id,
                expected=self.next_sequence,
                actual=sequence,
            )
        self.next_sequence = sequence + 1
        self.last_sequence = sequence

    @staticmethod
    def validate_sequence_list(sequences: List[int]) -> bool:
        """Check that a list of sequence numbers is gap-free.

        Returns True if valid. Raises EventSequenceGapError if a gap
        is found.
        """
        if not sequences:
            return True
        sorted_seqs = sorted(sequences)
        expected = sorted_seqs[0]
        for seq in sorted_seqs:
            if seq != expected:
                raise EventSequenceGapError(
                    "", expected=expected, actual=seq,
                )
            expected += 1
        return True

    @staticmethod
    def find_gaps(sequences: List[int]) -> List[int]:
        """Return a list of missing sequence numbers."""
        if not sequences:
            return []
        sorted_seqs = sorted(sequences)
        full_range = range(sorted_seqs[0], sorted_seqs[-1] + 1)
        return [s for s in full_range if s not in set(sorted_seqs)]
