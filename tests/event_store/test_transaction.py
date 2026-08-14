"""Event store transaction tests (Commit 34 Part 1.2 #6 / #7 / #11 / #14)."""

from __future__ import annotations

import pytest

from services.event_store.domain.errors import ConcurrencyConflictError


def test_commit_persists_changes(repository, make_events):
    transaction = repository.begin()
    transaction.append_stream("ORD-001", 0, make_events(versions=(1, 2)))
    transaction.commit()

    versions = [
        event.aggregate_version for event in repository.load_stream("ORD-001")
    ]
    assert versions == [1, 2]
    assert repository.current_version("ORD-001") == 2


def test_rollback_restores_previous_state(repository, make_events):
    repository.append_stream("ORD-001", 0, make_events(versions=(1,)))

    transaction = repository.begin()
    transaction.append_stream("ORD-001", 1, make_events(versions=(2,)))
    transaction.rollback()

    versions = [
        event.aggregate_version for event in repository.load_stream("ORD-001")
    ]
    assert versions == [1]
    assert repository.current_version("ORD-001") == 1


def test_atomic_multi_event_append(repository, make_events):
    transaction = repository.begin()
    transaction.append_stream("ORD-001", 0, make_events(versions=(1, 2, 3)))
    transaction.commit()

    versions = [
        event.aggregate_version for event in repository.load_stream("ORD-001")
    ]
    assert versions == [1, 2, 3]


def test_partial_failure_rolls_back_everything(repository, make_events):
    transaction = repository.begin()

    # the first append lands in the transaction
    transaction.append_stream("ORD-001", 0, make_events(versions=(1, 2)))

    # the second append breaks the sequence (v5 after v2)
    with pytest.raises(ValueError):
        transaction.append_stream("ORD-001", 2, make_events(versions=(5,)))

    transaction.rollback()

    # nothing - not even v1/v2 - survives the rollback
    assert list(repository.load_stream("ORD-001")) == []
    assert repository.current_version("ORD-001") == 0


def test_rollback_after_commit_is_noop(repository, make_events):
    transaction = repository.begin()
    transaction.append_stream("ORD-001", 0, make_events(versions=(1,)))
    transaction.commit()
    transaction.rollback()  # must not undo a committed transaction

    assert repository.current_version("ORD-001") == 1


def test_repository_append_stream_is_atomic(repository, make_events):
    # repository.append_stream wraps everything in a transaction: an invalid
    # batch must leave the store untouched
    with pytest.raises(ValueError):
        repository.append_stream(
            "ORD-001", 0, make_events(versions=(1, 2, 5))
        )

    assert list(repository.load_stream("ORD-001")) == []
    assert repository.current_version("ORD-001") == 0


def test_transaction_conflict_does_not_corrupt_store(repository, make_events):
    repository.append_stream("ORD-001", 0, make_events(versions=(1,)))

    transaction = repository.begin()
    transaction.append_stream("ORD-001", 1, make_events(versions=(2,)))
    with pytest.raises(ConcurrencyConflictError):
        transaction.append_stream("ORD-001", 1, make_events(versions=(3,)))
    transaction.rollback()

    versions = [
        event.aggregate_version for event in repository.load_stream("ORD-001")
    ]
    assert versions == [1]
