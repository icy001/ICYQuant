"""Durable command store with optimistic-concurrency CAS (§8-10, §31, §35-38)."""

from __future__ import annotations

import pytest

from services.control_plane.errors import (
    CommandRecordNotFound,
    DuplicateCommand,
    VersionConflict,
)
from services.control_plane.store import InMemoryCommandStore
from services.control_plane.transition import InvalidTransition


def test_create_and_get_roundtrip(make_record):
    store = InMemoryCommandStore()
    record = make_record(command_id="CMD-001", state="RECEIVED", version=1)
    store.create(record)
    assert store.get("CMD-001") == record


def test_duplicate_create_is_rejected(make_record):
    store = InMemoryCommandStore()
    store.create(make_record(command_id="CMD-001", version=1))
    with pytest.raises(DuplicateCommand):
        store.create(make_record(command_id="CMD-001", version=1))


def test_missing_record_raises_not_found():
    store = InMemoryCommandStore()
    with pytest.raises(CommandRecordNotFound):
        store.get("CMD-MISSING")


def test_transition_cas_increments_version(make_record):
    store = InMemoryCommandStore()
    store.create(make_record(command_id="CMD-001", state="RECEIVED", version=5))
    updated = store.transition("CMD-001", expected_version=5, new_state="AUTHORIZING")
    assert updated.state == "AUTHORIZING"
    assert updated.version == 6


def test_stale_version_raises_version_conflict(make_record):
    store = InMemoryCommandStore()
    store.create(make_record(command_id="CMD-001", state="EXECUTING", version=5))
    store.transition("CMD-001", expected_version=5, new_state="SUCCEEDED")
    with pytest.raises(VersionConflict):
        store.transition("CMD-001", expected_version=5, new_state="FAILED")


def test_concurrent_workers_last_writer_cannot_overwrite(make_record):
    """§37: two workers both see version=5; only one transition succeeds."""
    store = InMemoryCommandStore()
    store.create(make_record(command_id="CMD-001", state="EXECUTING", version=5))
    store.transition("CMD-001", expected_version=5, new_state="SUCCEEDED")
    with pytest.raises(VersionConflict):
        store.transition("CMD-001", expected_version=5, new_state="FAILED")
    assert store.get("CMD-001").state == "SUCCEEDED"


def test_history_records_every_transition(make_record):
    store = InMemoryCommandStore()
    store.create(make_record(command_id="CMD-001", state="RECEIVED", version=1))
    store.transition("CMD-001", expected_version=1, new_state="AUTHORIZING", reason="governance_check")
    store.transition("CMD-001", expected_version=2, new_state="AUTHORIZED", reason="governance_allow")
    store.transition("CMD-001", expected_version=3, new_state="DISPATCHING", reason="grant_valid")
    history = store.history("CMD-001")
    assert len(history) == 3
    assert history[0].from_state == "RECEIVED"
    assert history[0].to_state == "AUTHORIZING"
    assert history[0].version == 2
    assert history[1].reason == "governance_allow"
    assert history[2].to_state == "DISPATCHING"


def test_history_captures_unknown_recovery_path(make_record):
    store = InMemoryCommandStore()
    store.create(make_record(command_id="CMD-001", state="EXECUTING", version=1))
    store.transition("CMD-001", expected_version=1, new_state="UNKNOWN")
    store.transition("CMD-001", expected_version=2, new_state="RECOVERY_REQUIRED")
    store.transition("CMD-001", expected_version=3, new_state="SUCCEEDED")
    history = store.history("CMD-001")
    assert [h.to_state for h in history] == ["UNKNOWN", "RECOVERY_REQUIRED", "SUCCEEDED"]


def test_store_rejects_illegal_jump_before_persisting(make_record):
    store = InMemoryCommandStore()
    store.create(make_record(command_id="CMD-001", state="RECEIVED", version=1))
    with pytest.raises(InvalidTransition):
        store.transition("CMD-001", expected_version=1, new_state="SUCCEEDED")
    assert store.get("CMD-001").state == "RECEIVED"
    assert store.get("CMD-001").version == 1


def test_save_checkpoint_restores_after_crash(make_record):
    """§38: a crashed process restores the last checkpoint via ``save``."""
    store = InMemoryCommandStore()
    checkpoint = make_record(command_id="CMD-001", state="EXECUTING", version=7)
    store.save(checkpoint)
    assert store.get("CMD-001") == checkpoint
