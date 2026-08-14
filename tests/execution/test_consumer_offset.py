import pytest

from services.execution.domain.consumer import (
    ConsumerOffset,
)
from services.execution.infrastructure.memory_consumer_offset_store import (
    InMemoryConsumerOffsetStore,
)


def test_offset_is_saved():

    store = (
        InMemoryConsumerOffsetStore()
    )

    offset = ConsumerOffset(
        consumer_id="position-service",
        stream_id="exec-001",
        sequence=10,
    )

    store.save(offset)

    assert (
        store.get(
            "position-service",
            "exec-001",
        )
        == offset
    )


def test_offset_cannot_move_backwards():

    store = (
        InMemoryConsumerOffsetStore()
    )

    store.save(
        ConsumerOffset(
            consumer_id="position-service",
            stream_id="exec-001",
            sequence=10,
        )
    )

    with pytest.raises(ValueError):

        store.save(
            ConsumerOffset(
                consumer_id="position-service",
                stream_id="exec-001",
                sequence=9,
            )
        )
