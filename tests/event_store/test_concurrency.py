"""Optimistic concurrency control tests (Commit 34 Part 1.2 #4 / #13 / #14)."""

from __future__ import annotations

import pytest

from services.event_store.domain.errors import ConcurrencyConflictError


def test_expected_version_match_succeeds(repository, make_events):
    repository.append_stream("ORD-001", 0, make_events(versions=(1,)))
    repository.append_stream("ORD-001", 1, make_events(versions=(2,)))
    assert repository.current_version("ORD-001") == 2


def test_stale_version_rejected(repository, make_events):
    repository.append_stream("ORD-001", 0, make_events(versions=(1,)))
    with pytest.raises(ConcurrencyConflictError):
        repository.append_stream("ORD-001", 0, make_events(versions=(2,)))


def test_unknown_stream_requires_expected_zero(repository, make_events):
    with pytest.raises(ConcurrencyConflictError):
        repository.append_stream("ORD-001", 1, make_events(versions=(2,)))


def test_two_commands_same_expected_version(
    repository, make_events, make_stored_event
):
    # build the stream up to v7
    repository.append_stream("ORD-001", 0, make_events(versions=(1, 2, 3, 4, 5, 6, 7)))

    # command A commits first: v7 -> v8
    repository.append_stream(
        "ORD-001", 7, make_events(versions=(8,))
    )
    assert repository.current_version("ORD-001") == 8

    # command B was read at v7 as well; it carries its own brand-new event id.
    # It must be rejected - never silently overwrite A's result.
    b_event = make_stored_event(
        event_id="EVT-ORD-000108",
        aggregate_id="ORD-001",
        version=8,
    )
    with pytest.raises(ConcurrencyConflictError):
        repository.append_stream("ORD-001", 7, (b_event,))


def test_conflict_carries_version_context(repository, make_events):
    repository.append_stream("ORD-001", 0, make_events(versions=(1, 2)))
    with pytest.raises(ConcurrencyConflictError) as excinfo:
        repository.append_stream("ORD-001", 1, make_events(versions=(3,)))

    error = excinfo.value
    assert error.aggregate_id == "ORD-001"
    assert error.expected_version == 1
    assert error.actual_version == 2
    assert "ORD-001" in str(error)
    assert "expected_version=1" in str(error)
    assert "actual_version=2" in str(error)


def test_conflict_does_not_apply_events(repository, make_events):
    repository.append_stream("ORD-001", 0, make_events(versions=(1,)))
    with pytest.raises(ConcurrencyConflictError):
        repository.append_stream("ORD-001", 0, make_events(versions=(2,)))
    # the stale command left nothing behind
    stream = list(repository.load_stream("ORD-001"))
    assert [event.aggregate_version for event in stream] == [1]
    assert repository.current_version("ORD-001") == 1
