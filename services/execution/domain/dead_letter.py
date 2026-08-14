from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from services.execution.domain.event import (
    ExecutionEvent,
)


@dataclass(frozen=True)
class DeadLetterEvent:

    event: ExecutionEvent

    consumer_id: str

    attempts: int

    error: str

    created_at: datetime

    def validate(self) -> None:

        if not self.consumer_id:
            raise ValueError(
                "consumer_id is required"
            )

        if self.attempts <= 0:
            raise ValueError(
                "attempts must be positive"
            )

        if not self.error:
            raise ValueError(
                "error is required"
            )
