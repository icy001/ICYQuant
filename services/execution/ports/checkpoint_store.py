from __future__ import annotations

from abc import ABC, abstractmethod

from services.execution.domain.checkpoint import (
    ReplayCheckpoint,
)


class ReplayCheckpointStore(ABC):

    @abstractmethod
    def save(
        self,
        checkpoint: ReplayCheckpoint,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def get(
        self,
        execution_request_id: str,
    ) -> ReplayCheckpoint | None:
        raise NotImplementedError
