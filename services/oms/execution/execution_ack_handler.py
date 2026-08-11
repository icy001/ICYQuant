"""ExecutionAckHandler — processes ACKs from the execution layer."""
from __future__ import annotations

from typing import Dict, Optional

from .execution_response import ExecutionAck
from .execution_error import (
    ExecutionError,
    RequestIdReuseConflictError,
)


class ExecutionAckHandler:
    """Processes execution ACKs.

    Flow:
        ExecutionAck
             ↓
        Validate Request ID
             ↓
        Validate Order ID
             ↓
        Check Duplicate
             ↓
        Return result (for command generation)
    """

    def __init__(self) -> None:
        self._processed_acks: Dict[str, ExecutionAck] = {}

    def handle(self, ack: ExecutionAck) -> Dict:
        """Process an ACK. Returns a dict with processing result.

        Raises on conflicts. Idempotent replays return the original.
        """
        if not ack.request_id:
            raise ExecutionError(
                "ACK missing request_id",
                order_id=ack.order_id,
                code="MISSING_REQUEST_ID",
            )

        # Check for duplicate
        if ack.request_id in self._processed_acks:
            existing = self._processed_acks[ack.request_id]
            if (existing.status == ack.status
                    and existing.order_id == ack.order_id):
                # Idempotent replay
                return {
                    "status": "IDEMPOTENT_REPLAY",
                    "ack": existing,
                }
            else:
                raise RequestIdReuseConflictError(
                    ack.request_id, ack.order_id,
                )

        self._processed_acks[ack.request_id] = ack

        return {
            "status": "PROCESSED",
            "ack": ack,
            "accepted": ack.status.name == "ACCEPTED",
        }

    def is_processed(self, request_id: str) -> bool:
        return request_id in self._processed_acks

    def get_ack(self, request_id: str) -> Optional[ExecutionAck]:
        return self._processed_acks.get(request_id)
