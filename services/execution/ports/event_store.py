from __future__ import annotations

from abc import ABC, abstractmethod

from services.execution.domain.event import ExecutionEvent


class ExecutionEventStore(ABC):

    @abstractmethod
    def append(
        self,
        event: ExecutionEvent,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def get(
        self,
        event_id: str,
    ) -> ExecutionEvent | None:
        raise NotImplementedError

    @abstractmethod
    def stream(
        self,
        execution_request_id: str,
        *,
        after_sequence: int = 0,
    ) -> list[ExecutionEvent]:
        raise NotImplementedError

    @abstractmethod
    def latest_sequence(
        self,
        execution_request_id: str,
    ) -> int:
        raise NotImplementedError
