from __future__ import annotations

from abc import ABC, abstractmethod

from services.execution.domain.dead_letter import (
    DeadLetterEvent,
)


class DeadLetterStore(ABC):

    @abstractmethod
    def save(
        self,
        event: DeadLetterEvent,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def list(
        self,
        consumer_id: str | None = None,
    ) -> list[DeadLetterEvent]:
        raise NotImplementedError
