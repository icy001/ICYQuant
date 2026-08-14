from __future__ import annotations

from services.execution.domain.delivery import (
    DeliveryAttempt,
)
from services.execution.ports.delivery_store import (
    DeliveryStore,
)


class InMemoryDeliveryStore(
    DeliveryStore
):

    def __init__(self) -> None:

        self._items: dict[
            tuple[str, str, int],
            DeliveryAttempt,
        ] = {}

    def save(
        self,
        attempt: DeliveryAttempt,
    ) -> None:

        attempt.validate()

        key = (
            attempt.consumer_id,
            attempt.stream_id,
            attempt.sequence,
        )

        self._items[key] = attempt

    def latest(
        self,
        consumer_id: str,
        stream_id: str,
        sequence: int,
    ) -> DeliveryAttempt | None:

        return self._items.get(
            (
                consumer_id,
                stream_id,
                sequence,
            )
        )
