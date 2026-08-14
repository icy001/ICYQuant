import pytest

from services.execution.domain.checkpoint import (
    ReplayCheckpoint,
)
from services.execution.infrastructure.memory_checkpoint_store import (
    InMemoryReplayCheckpointStore,
)


def test_checkpoint_save():

    store = (
        InMemoryReplayCheckpointStore()
    )

    checkpoint = ReplayCheckpoint(
        execution_request_id="exec-001",
        sequence=10,
        state_version=10,
    )

    store.save(checkpoint)

    assert (
        store.get("exec-001")
        == checkpoint
    )


def test_checkpoint_cannot_move_backwards():

    store = (
        InMemoryReplayCheckpointStore()
    )

    store.save(
        ReplayCheckpoint(
            execution_request_id="exec-001",
            sequence=10,
            state_version=10,
        )
    )

    with pytest.raises(ValueError):

        store.save(
            ReplayCheckpoint(
                execution_request_id="exec-001",
                sequence=5,
                state_version=5,
            )
        )
