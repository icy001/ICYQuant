from __future__ import annotations

from services.execution.domain.event import (
    ExecutionEvent,
)
from services.execution.domain.journal import (
    ExecutionEventJournal,
)


class ExecutionEventJournalService:

    def __init__(
        self,
        journal: ExecutionEventJournal,
    ) -> None:
        self._journal = journal

    def record(
        self,
        event: ExecutionEvent,
    ) -> None:

        existing = self._journal.get(
            event.event_id
        )

        if existing is not None:
            raise ValueError(
                f"duplicate execution event: "
                f"{event.event_id}"
            )

        self._journal.append(event)

    def history(
        self,
        execution_request_id: str,
    ) -> list[ExecutionEvent]:

        return (
            self._journal
            .list_by_execution_request(
                execution_request_id
            )
        )
