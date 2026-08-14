from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ExecutionInstruction(str, Enum):
    IMMEDIATE = "IMMEDIATE"
    PASSIVE = "PASSIVE"
    AGGRESSIVE = "AGGRESSIVE"
    TWAP = "TWAP"
    VWAP = "VWAP"


@dataclass(frozen=True)
class ExecutionPolicy:
    instruction: ExecutionInstruction = (
        ExecutionInstruction.IMMEDIATE
    )

    max_slippage_bps: float | None = None

    timeout_seconds: int | None = None

    allow_partial_fill: bool = True

    def validate(self) -> None:
        if (
            self.max_slippage_bps is not None
            and self.max_slippage_bps < 0
        ):
            raise ValueError(
                "max_slippage_bps cannot be negative"
            )

        if (
            self.timeout_seconds is not None
            and self.timeout_seconds <= 0
        ):
            raise ValueError(
                "timeout_seconds must be positive"
            )
