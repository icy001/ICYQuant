from __future__ import annotations

from services.execution.ports.consumer_offset_store import (
    ConsumerOffsetStore,
)
from services.execution.ports.event_store import (
    ExecutionEventStore,
)


class ConsumerLagService:

    def __init__(
        self,
        event_store: ExecutionEventStore,
        offset_store: ConsumerOffsetStore,
    ) -> None:

        self._event_store = event_store
        self._offset_store = offset_store

    def lag(
        self,
        consumer_id: str,
        stream_id: str,
    ) -> int:

        latest = (
            self._event_store.latest_sequence(
                stream_id
            )
        )

        offset = self._offset_store.get(
            consumer_id,
            stream_id,
        )

        current = (
            offset.sequence
            if offset
            else 0
        )

        return max(
            latest - current,
            0,
        )
