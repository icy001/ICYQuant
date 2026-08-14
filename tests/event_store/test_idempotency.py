"""Idempotent persistence tests (Commit 34 Part 1.2 #9 / #14).

The store must recognise a client retry after a network timeout:

* same ``event_id`` + same payload  -> idempotent retry, accepted as no-op;
* same ``event_id`` + new payload   -> rejected (a fact never changes);
* a whole retried batch             -> no duplicates are written.
"""

from __future__ import annotations

import pytest

from services.event_store.domain.errors import (
    ConcurrencyConflictError,
    EventAlreadyExistsError,
)


def _versions(repository, aggregate_id="ORD-001"):
    return [
        event.aggregate_version
        for event in repository.load_stream(aggregate_id)
    ]


def test_duplicate_event_retry(repository, make_events):
    events = make_events(versions=(1,))
    repository.append_stream("ORD-001", 0, events)
    repository.append_stream("ORD-001", 0, events)  # retry, same batch

    assert _versions(repository) == [1]


def test_same_id_same_payload_is_retry(repository, make_stored_event):
    event = make_stored_event(payload={"status": "CREATED"})
    repository.append_stream("ORD-001", 0, (event,))
    retry = make_stored_event(payload={"status": "CREATED"})
    repository.append_stream("ORD-001", 0, (retry,))

    assert _versions(repository) == [1]
    assert repository.current_version("ORD-001") == 1


def test_same_id_different_payload_rejected(repository, make_stored_event):
    repository.append_stream(
        "ORD-001", 0, (make_stored_event(payload={"status": "CREATED"}),)
    )
    conflict = make_stored_event(payload={"status": "SUBMITTED"})

    with pytest.raises(EventAlreadyExistsError):
        repository.append_stream("ORD-001", 0, (conflict,))

    assert _versions(repository) == [1]
    assert repository.get("EVT-ORD-000001").payload == {"status": "CREATED"}


def test_duplicate_stream_append(repository, make_events):
    events = make_events(versions=(1, 2, 3))
    repository.append_stream("ORD-001", 0, events)
    repository.append_stream("ORD-001", 0, events)  # whole batch retried

    assert _versions(repository) == [1, 2, 3]
    assert len(repository.load_stream("ORD-001")) == 3


def test_retry_never_writes_copies(repository, make_events):
    events = make_events(versions=(1, 2))
    repository.append_stream("ORD-001", 0, events)
    repository.append_stream("ORD-001", 0, events)
    repository.append_stream("ORD-001", 0, events)

    event_ids = [event.event_id for event in repository.load_stream("ORD-001")]
    assert event_ids == ["EVT-ORD-000001", "EVT-ORD-000002"]


def test_new_events_after_retry_proceed(repository, make_events):
    first = make_events(versions=(1, 2))
    repository.append_stream("ORD-001", 0, first)
    repository.append_stream("ORD-001", 0, first)  # idempotent retry

    repository.append_stream("ORD-001", 2, make_events(versions=(3,)))
    assert _versions(repository) == [1, 2, 3]


def test_conflicting_retry_not_treated_as_idempotent(repository, make_events):
    events = make_events(versions=(1,))
    repository.append_stream("ORD-001", 0, events)

    # a *new* event id under a stale expected version is a real conflict,
    # not an idempotent retry
    with pytest.raises(ConcurrencyConflictError):
        repository.append_stream(
            "ORD-001", 0, make_events(versions=(2,))
        )
