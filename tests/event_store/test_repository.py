"""Event store repository tests (Commit 34 Part 1.1 #4 / #5 / #11)."""

from __future__ import annotations

import pytest

from services.event_store.domain.errors import (
    EventAlreadyExistsError,
    InvalidEventVersionError,
)
from services.event_store.infrastructure.memory_repository import (
    InMemoryEventStoreRepository,
)


@pytest.fixture
def repository() -> InMemoryEventStoreRepository:
    return InMemoryEventStoreRepository()


def test_get_event(repository, make_stored_event):
    event = make_stored_event()
    repository.append(event)
    assert repository.get("EVT-ORD-000001") == event


def test_get_missing_event_returns_none(repository):
    assert repository.get("EVT-ORD-999999") is None


def test_append_event(repository, make_stored_event):
    repository.append(make_stored_event())
    assert len(list(repository.load_stream("ORD-001"))) == 1


def test_load_stream(repository, make_stored_event):
    repository.append(make_stored_event(version=1))
    repository.append(make_stored_event(event_id="EVT-ORD-000002", version=2))
    stream = list(repository.load_stream("ORD-001"))
    assert len(stream) == 2


def test_append_duplicate_rejected(repository, make_stored_event):
    repository.append(make_stored_event())
    with pytest.raises(EventAlreadyExistsError):
        repository.append(make_stored_event())


def test_append_version_gap_rejected(repository, make_stored_event):
    repository.append(make_stored_event(version=1))
    with pytest.raises(InvalidEventVersionError):
        repository.append(make_stored_event(event_id="EVT-ORD-000003", version=3))


def test_append_is_append_only(repository, make_stored_event):
    # the append-only contract: no update / delete capabilities exist
    assert not hasattr(repository, "update")
    assert not hasattr(repository, "delete")
    repository.append(make_stored_event())
    with pytest.raises(EventAlreadyExistsError):
        repository.append(make_stored_event())
