from __future__ import annotations

from services.execution.domain.checkpoint import (
    ReplayCheckpoint,
)
from services.execution.ports.checkpoint_store import (
    ReplayCheckpointStore,
)


class InMemoryReplayCheckpointStore(
    ReplayCheckpointStore
):

    def __init__(self) -> None:
        self._checkpoints: dict[
            str,
            ReplayCheckpoint,
        ] = {}

    def save(
        self,
        checkpoint: ReplayCheckpoint,
    ) -> None:

        checkpoint.validate()

        current = self._checkpoints.get(
            checkpoint.execution_request_id
        )

        if (
            current is not None
            and checkpoint.sequence
            < current.sequence
        ):
            raise ValueError(
                "checkpoint sequence cannot move backwards"
            )

        self._checkpoints[
            checkpoint.execution_request_id
        ] = checkpoint

    def get(
        self,
        execution_request_id: str,
    ) -> ReplayCheckpoint | None:

        return self._checkpoints.get(
            execution_request_id
        )
