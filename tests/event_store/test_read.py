"""Read stream application service tests (Commit 34 Part 1.1 #8 / #11)."""

from __future__ import annotations

import pytest

from services.event_store.application.read import ReadEventStream
from services.event_store.infrastructure.memory_repository import (
    InMemoryEventStoreRepository,
)


@pytest.fixture
def stream_reader():
    def _factory():
        repository = InMemoryEventStoreRepository()
        return ReadEventStream(repository), repository

    return _factory


def test_read_aggregate_stream(stream_reader, make_stored_event):
    read, repository = stream_reader()
    repository.append(make_stored_event(version=1))
    repository.append(make_stored_event(event_id="EVT-ORD-000002", version=2))
    stream = list(read.execute("ORD-001"))
    assert len(stream) == 2


def test_read_empty_stream(stream_reader):
    read, _ = stream_reader()
    assert list(read.execute("ORD-001")) == []


def test_read_multiple_aggregates_are_isolated(stream_reader, make_stored_event):
    read, repository = stream_reader()
    repository.append(make_stored_event(version=1))
    repository.append(make_stored_event(event_id="EVT-ORD-000002", version=2))
    repository.append(
        make_stored_event(
            event_id="EVT-ORD-000003",
            aggregate_id="ORD-002",
            version=1,
        )
    )
    assert [event.event_id for event in read.execute("ORD-001")] == [
        "EVT-ORD-000001",
        "EVT-ORD-000002",
    ]
    assert [event.event_id for event in read.execute("ORD-002")] == [
        "EVT-ORD-000003",
    ]


def test_read_stream_ordering(stream_reader, make_stored_event):
    read, repository = stream_reader()
    repository.append(make_stored_event(version=1))
    repository.append(make_stored_event(event_id="EVT-ORD-000002", version=2))
    repository.append(make_stored_event(event_id="EVT-ORD-000003", version=3))
    versions = [event.aggregate_version for event in read.execute("ORD-001")]
    assert versions == [1, 2, 3]
