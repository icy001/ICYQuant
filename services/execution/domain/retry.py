from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    initial_delay_seconds: float = 1.0
    max_delay_seconds: float = 60.0
    multiplier: float = 2.0

    def validate(self) -> None:
        if self.max_attempts <= 0:
            raise ValueError(
                "max_attempts must be positive"
            )

        if self.initial_delay_seconds < 0:
            raise ValueError(
                "initial delay cannot be negative"
            )

        if self.max_delay_seconds < 0:
            raise ValueError(
                "max delay cannot be negative"
            )

        if self.multiplier < 1:
            raise ValueError(
                "multiplier must be >= 1"
            )

    def delay_for(
        self,
        attempt: int,
    ) -> float:

        if attempt <= 0:
            raise ValueError(
                "attempt must be positive"
            )

        delay = (
            self.initial_delay_seconds
            * (
                self.multiplier
                ** (attempt - 1)
            )
        )

        return min(
            delay,
            self.max_delay_seconds,
        )
