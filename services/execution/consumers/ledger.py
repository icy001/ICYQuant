from __future__ import annotations

from services.execution.application.event_consumer import (
    ExecutionEventConsumer,
)
from services.execution.domain.event import (
    ExecutionEvent,
)


class LedgerExecutionConsumer(
    ExecutionEventConsumer
):

    @property
    def consumer_id(self) -> str:
        return "ledger-service"

    def handle(
        self,
        event: ExecutionEvent,
    ) -> None:

        if event.filled_quantity <= 0:
            return

        # Ledger integration point.
        #
        # Ledger mutation belongs to Ledger Domain.
        return
