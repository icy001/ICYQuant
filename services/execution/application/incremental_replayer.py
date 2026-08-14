from __future__ import annotations

from services.execution.application.event_processor import (
    ExecutionEventProcessor,
)
from services.execution.domain.checkpoint import (
    ReplayCheckpoint,
)
from services.execution.domain.lifecycle import (
    ExecutionLifecycle,
)
from services.execution.domain.result import (
    ExecutionResult,
)
from services.execution.ports.checkpoint_store import (
    ReplayCheckpointStore,
)
from services.execution.ports.event_store import (
    ExecutionEventStore,
)


class IncrementalExecutionReplayer:

    def __init__(
        self,
        event_store: ExecutionEventStore,
        checkpoint_store: ReplayCheckpointStore,
        processor: ExecutionEventProcessor,
    ) -> None:

        self._event_store = event_store
        self._checkpoint_store = (
            checkpoint_store
        )
        self._processor = processor

    def replay(
        self,
        *,
        execution_request_id: str,
        requested_quantity: float,
        lifecycle: ExecutionLifecycle,
        result: ExecutionResult,
    ) -> int:

        checkpoint = (
            self._checkpoint_store.get(
                execution_request_id
            )
        )

        after_sequence = (
            checkpoint.sequence
            if checkpoint
            else 0
        )

        events = (
            self._event_store.stream(
                execution_request_id,
                after_sequence=after_sequence,
            )
        )

        last_sequence = after_sequence

        for event in events:

            self._processor.process(
                event,
                lifecycle,
                result,
            )

            last_sequence = event.sequence

        if last_sequence > after_sequence:

            self._checkpoint_store.save(
                ReplayCheckpoint(
                    execution_request_id=(
                        execution_request_id
                    ),
                    sequence=last_sequence,
                    state_version=last_sequence,
                )
            )

        return last_sequence
