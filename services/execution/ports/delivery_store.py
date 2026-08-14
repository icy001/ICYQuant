from __future__ import annotations

from abc import ABC, abstractmethod

from services.execution.domain.delivery import (
    DeliveryAttempt,
)


class DeliveryStore(ABC):

    @abstractmethod
    def save(
        self,
        attempt: DeliveryAttempt,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def latest(
        self,
        consumer_id: str,
        stream_id: str,
        sequence: int,
    ) -> DeliveryAttempt | None:
        raise NotImplementedError
