from __future__ import annotations

from abc import ABC, abstractmethod

from services.execution.domain.event import (
    ExecutionEvent,
)


class ExecutionEventConsumer(ABC):

    @property
    @abstractmethod
    def consumer_id(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def handle(
        self,
        event: ExecutionEvent,
    ) -> None:
        raise NotImplementedError
