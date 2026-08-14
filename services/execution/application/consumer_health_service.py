from __future__ import annotations

from services.execution.domain.consumer_health import (
    ConsumerHealth,
    ConsumerHealthStatus,
)
from services.execution.ports.consumer_offset_store import (
    ConsumerOffsetStore,
)


class ConsumerHealthService:

    def __init__(
        self,
        offset_store: ConsumerOffsetStore,
    ) -> None:

        self._offset_store = offset_store

    def healthy(
        self,
        consumer_id: str,
        stream_id: str,
    ) -> ConsumerHealth:

        offset = self._offset_store.get(
            consumer_id,
            stream_id,
        )

        sequence = (
            offset.sequence
            if offset
            else 0
        )

        return ConsumerHealth(
            consumer_id=consumer_id,
            status=(
                ConsumerHealthStatus.HEALTHY
            ),
            last_sequence=sequence,
        )
