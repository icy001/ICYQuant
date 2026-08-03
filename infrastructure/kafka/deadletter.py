"""
Dead Letter Queue.

Defines the dead letter message format
for events that have exhausted all retry
attempts and must be moved to the DLQ.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class DeadLetterMessage:
    """
    Dead letter queue message.

    Represents an event that has failed all
    retry attempts and is forwarded to the
    dead letter queue for manual inspection.

    Attributes:
        topic: Original Kafka topic.
        reason: Failure reason description.
        payload: Original message payload.
        headers: Additional metadata (retries, timestamps).
    """

    topic: str = ""

    reason: str = ""

    payload: bytes = b""

    headers: Dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(
        self,
    ) -> Dict[str, Any]:
        """
        Serialize to dictionary.

        Returns:
            Dictionary representation.
        """

        return {
            "topic": self.topic,
            "reason": self.reason,
            "payload": self.payload.decode(
                "utf-8"
            )
            if isinstance(
                self.payload, bytes
            )
            else self.payload,
            "headers": self.headers,
        }

    @classmethod
    def create(
        cls,
        topic: str,
        reason: str,
        payload: bytes,
        retry_count: int = 0,
        original_event_id: str = "",
    ) -> DeadLetterMessage:
        """
        Create a new dead letter message.

        Args:
            topic: Original Kafka topic.
            reason: Failure reason.
            payload: Original message bytes.
            retry_count: Number of retries attempted.
            original_event_id: Original event ID.

        Returns:
            New DeadLetterMessage instance.
        """

        return cls(
            topic=topic,
            reason=reason,
            payload=payload,
            headers={
                "retry_count": retry_count,
                "original_event_id": (
                    original_event_id
                ),
                "dlq_timestamp": (
                    __import__("datetime")
                    .datetime.utcnow()
                    .isoformat()
                ),
            },
        )
