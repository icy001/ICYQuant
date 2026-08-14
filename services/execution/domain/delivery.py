from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DeliveryStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    DELIVERED = "DELIVERED"
    RETRYING = "RETRYING"
    DEAD_LETTERED = "DEAD_LETTERED"


@dataclass(frozen=True)
class DeliveryAttempt:
    consumer_id: str
    stream_id: str
    sequence: int
    attempt: int
    status: DeliveryStatus
    error: str | None = None

    def validate(self) -> None:
        if not self.consumer_id:
            raise ValueError(
                "consumer_id is required"
            )

        if not self.stream_id:
            raise ValueError(
                "stream_id is required"
            )

        if self.sequence <= 0:
            raise ValueError(
                "sequence must be positive"
            )

        if self.attempt <= 0:
            raise ValueError(
                "attempt must be positive"
            )
