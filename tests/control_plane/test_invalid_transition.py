"""Illegal lifecycle jumps are rejected before they can be persisted (§4)."""

from __future__ import annotations

import pytest

from services.control_plane.store import InMemoryCommandStore
from services.control_plane.transition import InvalidTransition, StateTransitionEngine


@pytest.mark.parametrize(
    ("current", "target"),
    [
        ("RECEIVED", "SUCCEEDED"),
        ("EXECUTING", "AUTHORIZED"),
        ("REJECTED", "EXECUTING"),
        ("SUCCEEDED", "EXECUTING"),
        ("FAILED", "EXECUTING"),
        ("DISPATCHING", "AUTHORIZED"),
        ("AUTHORIZED", "EXECUTING"),
        ("WAITING_APPROVAL", "DISPATCHING"),
        ("MANUAL_INTERVENTION", "EXECUTING"),
        ("UNKNOWN", "SUCCEEDED"),
    ],
)
def test_illegal_jumps_raise_invalid_transition(current, target):
    engine = StateTransitionEngine()
    with pytest.raises(InvalidTransition, match=f"{current} -> {target}"):
        engine.transition(current, target)


def test_unknown_current_state_fails_closed():
    engine = StateTransitionEngine()
    with pytest.raises(InvalidTransition):
        engine.transition("BOGUS", "SUCCEEDED")


def test_store_refuses_illegal_jump_as_defense_in_depth(make_record):
    """Even the persistence layer refuses to persist an illegal jump (§45.1)."""
    store = InMemoryCommandStore()
    record = make_record(command_id="CMD-001", state="RECEIVED", version=1)
    store.create(record)
    with pytest.raises(InvalidTransition, match="RECEIVED -> SUCCEEDED"):
        store.transition("CMD-001", expected_version=1, new_state="SUCCEEDED")


def test_store_does_not_mutate_on_illegal_jump(make_record):
    store = InMemoryCommandStore()
    record = make_record(command_id="CMD-001", state="RECEIVED", version=1)
    store.create(record)
    with pytest.raises(InvalidTransition):
        store.transition("CMD-001", expected_version=1, new_state="SUCCEEDED")
    assert store.get("CMD-001").state == "RECEIVED"
    assert store.get("CMD-001").version == 1
