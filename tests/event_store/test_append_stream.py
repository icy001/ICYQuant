"""AppendEventStream application service tests (Commit 34 Part 1.2 #6 / #8 / #14)."""

from __future__ import annotations

import pytest

from services.event_store.application.append_stream import AppendEventStream
from services.event_store.domain.errors import ConcurrencyConflictError
from services.event_store.infrastructure.memory_repository import (
    InMemoryEventStoreRepository,
)


@pytest.fixture
def append_stream_with_repo():
    def _factory():
        repository = InMemoryEventStoreRepository()
        return AppendEventStream(repository), repository

    return _factory


def test_multi_event_append(append_stream_with_repo, make_events):
    append_stream, repository = append_stream_with_repo()
    append_stream.execute("ORD-001", 0, make_events(versions=(1, 2, 3)))

    versions = [
        event.aggregate_version for event in repository.load_stream("ORD-001")
    ]
    assert versions == [1, 2, 3]
    assert repository.current_version("ORD-001") == 3


def test_empty_stream_append(append_stream_with_repo, make_events):
    append_stream, repository = append_stream_with_repo()
    append_stream.execute("ORD-001", 0, make_events(versions=(1,)))
    assert repository.current_version("ORD-001") == 1


def test_append_after_existing_stream(append_stream_with_repo, make_events):
    append_stream, repository = append_stream_with_repo()
    append_stream.execute("ORD-001", 0, make_events(versions=(1, 2)))
    append_stream.execute("ORD-001", 2, make_events(versions=(3,)))
    assert repository.current_version("ORD-001") == 3


def test_invalid_sequence_rejected(append_stream_with_repo, make_events):
    append_stream, repository = append_stream_with_repo()
    # v1 -> v3 skips v2
    with pytest.raises(ValueError):
        append_stream.execute("ORD-001", 0, make_events(versions=(1, 3)))
    assert list(repository.load_stream("ORD-001")) == []


def test_invalid_sequence_start_rejected(append_stream_with_repo, make_events):
    append_stream, repository = append_stream_with_repo()
    # the first event of an empty stream must be v1
    with pytest.raises(ValueError):
        append_stream.execute("ORD-001", 0, make_events(versions=(2,)))
    assert list(repository.load_stream("ORD-001")) == []


def test_stale_expected_version_rejected(append_stream_with_repo, make_events):
    append_stream, repository = append_stream_with_repo()
    append_stream.execute("ORD-001", 0, make_events(versions=(1,)))
    with pytest.raises(ConcurrencyConflictError):
        append_stream.execute("ORD-001", 0, make_events(versions=(2,)))
