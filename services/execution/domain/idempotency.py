from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionIdempotencyKey:
    key: str

    def __post_init__(self) -> None:
        if not self.key:
            raise ValueError(
                "idempotency key is required"
            )
