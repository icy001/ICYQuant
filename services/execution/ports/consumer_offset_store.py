from __future__ import annotations

from abc import ABC, abstractmethod

from services.execution.domain.consumer import (
    ConsumerOffset,
)


class ConsumerOffsetStore(ABC):

    @abstractmethod
    def get(
        self,
        consumer_id: str,
        stream_id: str,
    ) -> ConsumerOffset | None:
        raise NotImplementedError

    @abstractmethod
    def save(
        self,
        offset: ConsumerOffset,
    ) -> None:
        raise NotImplementedError
