from datetime import datetime

import pytest

from services.execution.domain.event import (
    ExecutionEvent,
    ExecutionEventType,
)
from services.execution.infrastructure.memory_journal import (
    InMemoryExecutionEventJournal,
)


def build_event(
    event_id="event-001",
    request_id="exec-001",
):
    return ExecutionEvent(
        event_id=event_id,
        execution_request_id=request_id,
        order_id="order-001",
        event_type=ExecutionEventType.FILLED,
        timestamp=datetime.now(),
        sequence=1,
    )


def test_event_can_be_persisted():

    journal = (
        InMemoryExecutionEventJournal()
    )

    event = build_event(
        event_id="event-001",
        request_id="exec-001",
    )

    journal.append(event)

    stored = journal.get(
        "event-001"
    )

    assert stored == event


def test_duplicate_event_is_rejected():

    journal = (
        InMemoryExecutionEventJournal()
    )

    event = build_event(
        event_id="event-001",
        request_id="exec-001",
    )

    journal.append(event)

    with pytest.raises(ValueError):
        journal.append(event)


def test_request_history():

    journal = (
        InMemoryExecutionEventJournal()
    )

    event_1 = build_event(
        event_id="event-001",
        request_id="exec-001",
    )

    event_2 = build_event(
        event_id="event-002",
        request_id="exec-001",
    )

    journal.append(event_1)
    journal.append(event_2)

    history = (
        journal
        .list_by_execution_request(
            "exec-001"
        )
    )

    assert len(history) == 2
    assert history[0] == event_1
    assert history[1] == event_2
