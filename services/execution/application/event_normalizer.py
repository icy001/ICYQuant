from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from services.execution.domain.event import (
    ExecutionEvent,
    ExecutionEventType,
)
from services.execution.domain.fill import (
    ExecutionFill,
)


class ExecutionEventNormalizer:

    def fill_to_event(
        self,
        fill: ExecutionFill,
        *,
        requested_quantity: float,
        cumulative_quantity: float,
    ) -> ExecutionEvent:

        remaining = max(
            requested_quantity
            - cumulative_quantity,
            0.0,
        )

        event_type = (
            ExecutionEventType.FILLED
            if remaining == 0
            else ExecutionEventType.PARTIAL_FILL
        )

        return ExecutionEvent(
            event_id=str(uuid4()),
            execution_request_id=(
                fill.execution_request_id
            ),
            order_id=fill.order_id,
            event_type=event_type,
            timestamp=fill.timestamp,
            external_order_id=(
                fill.external_order_id
            ),
            execution_id=fill.execution_id,
            filled_quantity=fill.quantity,
            fill_price=fill.price,
            cumulative_filled_quantity=(
                cumulative_quantity
            ),
            remaining_quantity=remaining,
            venue_id=fill.venue_id,
        )
