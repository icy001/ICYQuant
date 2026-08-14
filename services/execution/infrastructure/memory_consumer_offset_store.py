from __future__ import annotations

from services.execution.domain.consumer import (
    ConsumerOffset,
)
from services.execution.ports.consumer_offset_store import (
    ConsumerOffsetStore,
)


class InMemoryConsumerOffsetStore(
    ConsumerOffsetStore
):

    def __init__(self) -> None:
        self._offsets: dict[
            tuple[str, str],
            ConsumerOffset,
        ] = {}

    def get(
        self,
        consumer_id: str,
        stream_id: str,
    ) -> ConsumerOffset | None:

        return self._offsets.get(
            (
                consumer_id,
                stream_id,
            )
        )

    def save(
        self,
        offset: ConsumerOffset,
    ) -> None:

        offset.validate()

        key = (
            offset.consumer_id,
            offset.stream_id,
        )

        current = self._offsets.get(key)

        if (
            current is not None
            and offset.sequence
            < current.sequence
        ):
            raise ValueError(
                "consumer offset cannot move backwards"
            )

        self._offsets[key] = offset
