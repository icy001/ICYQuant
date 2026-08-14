from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionEventSequence:
    sequence: int

    def __post_init__(self) -> None:
        if self.sequence <= 0:
            raise ValueError(
                "sequence must be positive"
            )
