from __future__ import annotations

from services.execution.domain.fill import (
    ExecutionFill,
)


class DuplicateFillError(
    ValueError
):
    pass


class FillDeduplicator:

    def __init__(self) -> None:
        self._seen: set[str] = set()

    def check(
        self,
        fill: ExecutionFill,
    ) -> None:

        if fill.execution_id in self._seen:
            raise DuplicateFillError(
                f"duplicate execution: "
                f"{fill.execution_id}"
            )

        self._seen.add(
            fill.execution_id
        )
