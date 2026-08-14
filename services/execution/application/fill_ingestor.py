from __future__ import annotations

from services.execution.application.event_normalizer import (
    ExecutionEventNormalizer,
)
from services.execution.domain.event import (
    ExecutionEvent,
)
from services.execution.domain.fill import (
    ExecutionFill,
)


class FillIngestor:

    def __init__(
        self,
        normalizer: ExecutionEventNormalizer | None = None,
    ) -> None:

        self._normalizer = (
            normalizer
            or ExecutionEventNormalizer()
        )

    def ingest(
        self,
        fill: ExecutionFill,
        *,
        requested_quantity: float,
        cumulative_quantity: float,
    ) -> ExecutionEvent:

        fill.validate()

        return self._normalizer.fill_to_event(
            fill,
            requested_quantity=requested_quantity,
            cumulative_quantity=cumulative_quantity,
        )
