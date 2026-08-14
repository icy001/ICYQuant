from __future__ import annotations

from services.execution.application.event_processor import (
    ExecutionEventProcessor,
)
from services.execution.domain.event import (
    ExecutionEvent,
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


class ExecutionEventReplayer:

    def __init__(
        self,
        processor: ExecutionEventProcessor | None = None,
    ) -> None:
        self._processor = (
            processor
            or ExecutionEventProcessor()
        )

    def replay(
        self,
        events: list[ExecutionEvent],
        *,
        requested_quantity: float,
    ) -> tuple[
        ExecutionLifecycle,
        ExecutionResult,
    ]:

        lifecycle = ExecutionLifecycle(
            state=ExecutionState.SUBMITTED
        )

        result = ExecutionResult(
            requested_quantity=requested_quantity
        )

        for event in events:
            self._processor.process(
                event,
                lifecycle,
                result,
            )

        return lifecycle, result
