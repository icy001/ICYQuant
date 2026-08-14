from __future__ import annotations

from abc import ABC, abstractmethod

from services.execution.domain.event import ExecutionEvent


class ExecutionEventJournal(ABC):
    """
    Durable journal for execution events.
    """

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
    def list_by_execution_request(
        self,
        execution_request_id: str,
    ) -> list[ExecutionEvent]:
        raise NotImplementedError
