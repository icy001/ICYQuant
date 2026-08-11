"""FIX Sequence Manager — FIX message sequence number management.

Tracks inbound and outbound message sequence numbers per FIX session.
Detects sequence gaps and manages sequence reset/recovery.

Sequence Rules:
    - Outbound: monotonically increasing, reset on Logon
    - Inbound: validated for gaps, reset on Logon
    - Gap detected → ResendRequest → Recovery

Usage::

    seq_mgr = FIXSequenceManager()
    seq_mgr.next_outgoing()  # Returns next outbound seq
    seq_mgr.next_incoming()  # Validates + increments inbound seq
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class FIXSequenceManager:
    """FIX sequence number manager.

    Tracks inbound and outbound sequence numbers and detects
    sequence gaps that require recovery.

    Attributes:
        sequence_out: Next outbound sequence number
        sequence_in: Expected next inbound sequence number
        _initialized: Whether sequence has been initialized
        _gap_count: Number of gaps detected
    """

    def __init__(self) -> None:
        self.sequence_out: int = 1
        self.sequence_in: int = 1
        self._initialized = False
        self._gap_count = 0
        self._last_reset_at: float = 0.0

    # ── Sequence Operations ────────────────────────────────────────

    def reset(self) -> None:
        """Reset sequence numbers (on Logon)."""
        import time
        self.sequence_out = 1
        self.sequence_in = 1
        self._initialized = True
        self._last_reset_at = time.time()
        logger.debug("Sequence numbers reset: out=1, in=1")

    def next_outgoing(self) -> int:
        """Get and increment outbound sequence number.

        Returns:
            Current outbound sequence number
        """
        current = self.sequence_out
        self.sequence_out += 1
        return current

    def next_incoming(self, expected_seq: int = 0) -> tuple[int, bool]:
        """Validate and increment inbound sequence number.

        Args:
            expected_seq: Expected sequence number (0 = use internal)

        Returns:
            (sequence_number, is_expected)
        """
        expected = expected_seq if expected_seq > 0 else self.sequence_in

        current = self.sequence_in
        self.sequence_in += 1

        is_expected = current == expected

        if not is_expected and current > expected:
            # Gap detected: messages skipped
            gap_size = current - expected
            self._gap_count += 1
            logger.warning(
                "Sequence gap detected: expected %d, got %d (gap=%d)",
                expected,
                current,
                gap_size,
            )

        return current, is_expected

    def set_outgoing(self, seq_num: int) -> None:
        """Set outbound sequence number.

        Args:
            seq_num: New outbound sequence number
        """
        if seq_num > self.sequence_out:
            logger.info("Outbound sequence set to %d", seq_num)
        self.sequence_out = max(seq_num, 1)

    def set_incoming(self, seq_num: int) -> None:
        """Set expected inbound sequence number.

        Args:
            seq_num: Expected next inbound sequence number
        """
        if seq_num > self.sequence_in:
            logger.info("Inbound sequence set to %d", seq_num)
        self.sequence_in = max(seq_num, 1)

    # ── Gap Detection ──────────────────────────────────────────────

    def check_gap(
        self,
        received_seq: int,
    ) -> tuple[bool, int, int]:
        """Check for sequence gap.

        Args:
            received_seq: Received message sequence number

        Returns:
            (has_gap, expected_seq, gap_size)
        """
        if received_seq == self.sequence_in:
            return False, self.sequence_in, 0

        gap_size = received_seq - self.sequence_in
        if gap_size > 0:
            return True, self.sequence_in, gap_size
        elif gap_size < 0:
            # Duplicate or late message
            logger.debug("Possible duplicate message: seq=%d, expected=%d", received_seq, self.sequence_in)
            return False, self.sequence_in, 0

        return False, self.sequence_in, 0

    def get_resend_range(self, received_seq: int) -> tuple[int, int]:
        """Get the range of messages to resend.

        Args:
            received_seq: Received sequence number (ahead)

        Returns:
            (begin_seq, end_seq) for ResendRequest
        """
        return self.sequence_in, received_seq - 1

    # ── Properties ─────────────────────────────────────────────────

    @property
    def gap_count(self) -> int:
        return self._gap_count

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    def to_dict(self) -> dict[str, Any]:
        """Serialize sequence state."""
        return {
            "sequence_out": self.sequence_out,
            "sequence_in": self.sequence_in,
            "initialized": self._initialized,
            "gap_count": self._gap_count,
        }
