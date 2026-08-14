from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReplayCheckpoint:

    execution_request_id: str

    sequence: int

    state_version: int

    def validate(self) -> None:

        if not self.execution_request_id:
            raise ValueError(
                "execution_request_id is required"
            )

        if self.sequence < 0:
            raise ValueError(
                "sequence cannot be negative"
            )

        if self.state_version < 0:
            raise ValueError(
                "state_version cannot be negative"
            )
