from __future__ import annotations

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


class ExecutionEventProcessor:

    def process(
        self,
        event: ExecutionEvent,
        lifecycle: ExecutionLifecycle,
        result: ExecutionResult,
    ) -> None:

        if event.event_type == (
            ExecutionEventType.PARTIAL_FILL
        ):
            lifecycle.transition(
                ExecutionState.PARTIALLY_FILLED
            )

            result.apply_fill(
                quantity=event.filled_quantity,
                price=event.fill_price,
            )

        elif event.event_type == (
            ExecutionEventType.FILLED
        ):
            result.apply_fill(
                quantity=event.filled_quantity,
                price=event.fill_price,
            )

            lifecycle.transition(
                ExecutionState.FILLED
            )

        elif event.event_type == (
            ExecutionEventType.CANCELLED
        ):
            lifecycle.transition(
                ExecutionState.CANCELLED
            )

        elif event.event_type == (
            ExecutionEventType.REJECTED
        ):
            lifecycle.transition(
                ExecutionState.REJECTED
            )

        elif event.event_type == (
            ExecutionEventType.EXPIRED
        ):
            lifecycle.transition(
                ExecutionState.EXPIRED
            )
