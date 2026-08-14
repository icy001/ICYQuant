from __future__ import annotations

from services.execution.application.event_journal_service import (
    ExecutionEventJournalService,
)
from services.execution.application.event_processor import (
    ExecutionEventProcessor,
)
from services.execution.application.fill_deduplicator import (
    DuplicateFillError,
    FillDeduplicator,
)
from services.execution.domain.event import (
    ExecutionEvent,
)
from services.execution.domain.fill import (
    ExecutionFill,
)
from services.execution.domain.lifecycle import (
    ExecutionLifecycle,
)
from services.execution.domain.result import (
    ExecutionResult,
)


class DurableFillIngestor:

    def __init__(
        self,
        journal_service: ExecutionEventJournalService,
        deduplicator: FillDeduplicator,
        processor: ExecutionEventProcessor,
    ) -> None:
        self._journal = journal_service
        self._deduplicator = deduplicator
        self._processor = processor

    def ingest(
        self,
        *,
        fill: ExecutionFill,
        event: ExecutionEvent,
        lifecycle: ExecutionLifecycle,
        result: ExecutionResult,
    ) -> None:

        try:
            self._deduplicator.check(fill)
        except DuplicateFillError:
            return

        self._journal.record(event)

        self._processor.process(
            event,
            lifecycle,
            result,
        )
