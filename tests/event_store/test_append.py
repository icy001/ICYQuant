"""Append event application service tests (Commit 34 Part 1.1 #5 / #7)."""

from __future__ import annotations

import pytest

from services.event_store.application.append import AppendEvent
from services.event_store.domain.errors import (
    EventAlreadyExistsError,
    InvalidEventVersionError,
)
from services.event_store.infrastructure.memory_repository import (
    InMemoryEventStoreRepository,
)


@pytest.fixture
def append_with_repo():
    def _factory():
        repository = InMemoryEventStoreRepository()
        return AppendEvent(repository), repository

    return _factory


def test_append_first_event(append_with_repo, make_stored_event):
    append, repository = append_with_repo()
    append.execute(make_stored_event())
    assert repository.get("EVT-ORD-000001") is not None


def test_append_sequential_event(append_with_repo, make_stored_event):
    append, repository = append_with_repo()
    append.execute(make_stored_event(version=1))
    append.execute(make_stored_event(event_id="EVT-ORD-000002", version=2))
    assert len(list(repository.load_stream("ORD-001"))) == 2


def test_append_duplicate_event(append_with_repo, make_stored_event):
    append, _ = append_with_repo()
    append.execute(make_stored_event())
    with pytest.raises(EventAlreadyExistsError):
        append.execute(make_stored_event())


def test_append_invalid_version_jump(append_with_repo, make_stored_event):
    append, _ = append_with_repo()
    append.execute(make_stored_event(version=1))
    with pytest.raises(InvalidEventVersionError):
        append.execute(make_stored_event(event_id="EVT-ORD-000003", version=3))


def test_append_invalid_version_repeat(append_with_repo, make_stored_event):
    # a different event_id carrying an already-used version is a version error,
    # not a duplicate-id error (#5: v2 -> v2 is rejected)
    append, _ = append_with_repo()
    append.execute(make_stored_event(version=1))
    append.execute(make_stored_event(event_id="EVT-ORD-000002", version=2))
    with pytest.raises(InvalidEventVersionError):
        append.execute(make_stored_event(event_id="EVT-ORD-000003", version=2))
