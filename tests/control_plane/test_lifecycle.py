"""CommandLifecycle is the only place command state may change (§7)."""

from __future__ import annotations

import pytest

from services.control_plane.lifecycle import CommandLifecycle
from services.control_plane.transition import InvalidTransition, StateTransitionEngine


@pytest.fixture
def lifecycle():
    return CommandLifecycle(StateTransitionEngine())


def test_move_validates_and_updates_state(lifecycle, mutable_command):
    assert mutable_command.state == "RECEIVED"
    lifecycle.move(mutable_command, "AUTHORIZING")
    assert mutable_command.state == "AUTHORIZING"


def test_move_returns_same_command_object(lifecycle, mutable_command):
    result = lifecycle.move(mutable_command, "AUTHORIZING")
    assert result is mutable_command


def test_move_invalid_target_raises_and_keeps_state(lifecycle, mutable_command):
    with pytest.raises(InvalidTransition):
        lifecycle.move(mutable_command, "SUCCEEDED")
    assert mutable_command.state == "RECEIVED"


def test_lifecycle_tracks_full_execution(lifecycle, mutable_command):
    for target in ("AUTHORIZING", "AUTHORIZED", "DISPATCHING", "EXECUTING", "SUCCEEDED"):
        lifecycle.move(mutable_command, target)
    assert mutable_command.state == "SUCCEEDED"


def test_lifecycle_tracks_unknown_recovery_path(lifecycle, mutable_command):
    for target in ("AUTHORIZING", "AUTHORIZED", "DISPATCHING", "EXECUTING", "UNKNOWN"):
        lifecycle.move(mutable_command, target)
    lifecycle.move(mutable_command, "RECOVERY_REQUIRED")
    lifecycle.move(mutable_command, "SUCCEEDED")
    assert mutable_command.state == "SUCCEEDED"


def test_lifecycle_moves_durable_records(make_record, lifecycle):
    """The lifecycle also moves the durable record view (Part 1.3 §7)."""

    class MutableRecord:
        def __init__(self, record) -> None:
            self.command_id = record.command_id
            self.state = record.state

    record = MutableRecord(make_record(state="RECEIVED"))
    lifecycle.move(record, "AUTHORIZING")
    assert record.state == "AUTHORIZING"
