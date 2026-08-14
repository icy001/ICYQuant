from datetime import datetime

from services.execution.application.event_processor import (
    ExecutionEventProcessor,
)
from services.execution.application.incremental_replayer import (
    IncrementalExecutionReplayer,
)
from services.execution.domain.checkpoint import (
    ReplayCheckpoint,
)
from services.execution.domain.event import (
    ExecutionEvent,
    ExecutionEventType,
)
from services.execution.domain.lifecycle import (
    ExecutionLifecycle,
)
from services.execution.domain.result import (
    ExecutionResult,
)
from services.execution.domain.state import (
    ExecutionState,
)
from services.execution.infrastructure.memory_checkpoint_store import (
    InMemoryReplayCheckpointStore,
)
from services.execution.infrastructure.memory_event_store import (
    InMemoryExecutionEventStore,
)


def build_event(
    event_id="event-1",
    request_id="exec-001",
    sequence=1,
    event_type=ExecutionEventType.ACCEPTED,
    filled_quantity=0.0,
    fill_price=None,
    cumulative_filled_quantity=0.0,
):
    return ExecutionEvent(
        event_id=event_id,
        execution_request_id=request_id,
        order_id="order-001",
        event_type=event_type,
        timestamp=datetime.now(),
        filled_quantity=filled_quantity,
        fill_price=fill_price,
        cumulative_filled_quantity=(
            cumulative_filled_quantity
        ),
        sequence=sequence,
    )


def test_replay_only_processes_new_events():

    event_store = (
        InMemoryExecutionEventStore()
    )

    checkpoint_store = (
        InMemoryReplayCheckpointStore()
    )

    for sequence in range(1, 4):

        event_store.append(
            build_event(
                event_id=(
                    f"event-{sequence}"
                ),
                request_id="exec-001",
                sequence=sequence,
            )
        )

    checkpoint_store.save(
        ReplayCheckpoint(
            execution_request_id="exec-001",
            sequence=2,
            state_version=2,
        )
    )

    replayer = IncrementalExecutionReplayer(
        event_store=event_store,
        checkpoint_store=checkpoint_store,
        processor=ExecutionEventProcessor(),
    )

    lifecycle = ExecutionLifecycle()

    result = ExecutionResult(
        requested_quantity=100
    )

    sequence = replayer.replay(
        execution_request_id="exec-001",
        requested_quantity=100,
        lifecycle=lifecycle,
        result=result,
    )

    assert sequence == 3

    checkpoint = (
        checkpoint_store.get(
            "exec-001"
        )
    )

    assert checkpoint.sequence == 3


def test_replay_rebuilds_state_from_checkpoint():

    event_store = (
        InMemoryExecutionEventStore()
    )

    checkpoint_store = (
        InMemoryReplayCheckpointStore()
    )

    for sequence in range(1, 3):

        event_store.append(
            build_event(
                event_id=(
                    f"event-{sequence}"
                ),
                request_id="exec-001",
                sequence=sequence,
            )
        )

    event_store.append(
        build_event(
            event_id="event-3",
            request_id="exec-001",
            sequence=3,
            event_type=(
                ExecutionEventType.PARTIAL_FILL
            ),
            filled_quantity=400,
            fill_price=100.0,
            cumulative_filled_quantity=400,
        )
    )

    event_store.append(
        build_event(
            event_id="event-4",
            request_id="exec-001",
            sequence=4,
            event_type=(
                ExecutionEventType.FILLED
            ),
            filled_quantity=600,
            fill_price=102.0,
            cumulative_filled_quantity=1000,
        )
    )

    checkpoint_store.save(
        ReplayCheckpoint(
            execution_request_id="exec-001",
            sequence=2,
            state_version=2,
        )
    )

    replayer = IncrementalExecutionReplayer(
        event_store=event_store,
        checkpoint_store=checkpoint_store,
        processor=ExecutionEventProcessor(),
    )

    lifecycle = ExecutionLifecycle(
        state=ExecutionState.SUBMITTED
    )

    result = ExecutionResult(
        requested_quantity=1000
    )

    sequence = replayer.replay(
        execution_request_id="exec-001",
        requested_quantity=1000,
        lifecycle=lifecycle,
        result=result,
    )

    assert sequence == 4

    assert result.filled_quantity == 1000
    assert result.remaining_quantity == 0
    assert result.fully_filled

    assert (
        lifecycle.state
        == ExecutionState.FILLED
    )

    checkpoint = (
        checkpoint_store.get(
            "exec-001"
        )
    )

    assert checkpoint.sequence == 4
