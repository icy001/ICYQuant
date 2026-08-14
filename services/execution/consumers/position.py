from __future__ import annotations

from services.execution.application.event_consumer import (
    ExecutionEventConsumer,
)
from services.execution.domain.event import (
    ExecutionEvent,
)


class PositionExecutionConsumer(
    ExecutionEventConsumer
):

    @property
    def consumer_id(self) -> str:
        return "position-service"

    def handle(
        self,
        event: ExecutionEvent,
    ) -> None:

        if event.filled_quantity <= 0:
            return

        # Position Service integration point.
        #
        # Actual position mutation will be handled
        # by Position Domain.
        return
