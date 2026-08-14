from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ConsumerOffset:
    consumer_id: str
    stream_id: str
    sequence: int = 0

    def validate(self) -> None:
        if not self.consumer_id:
            raise ValueError(
                "consumer_id is required"
            )

        if not self.stream_id:
            raise ValueError(
                "stream_id is required"
            )

        if self.sequence < 0:
            raise ValueError(
                "sequence cannot be negative"
            )
