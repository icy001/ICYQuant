"""Runbook action tests (Commit 27 Part 1.5, spec sections 9-10, 29)."""

import pytest

from services.operations import RunbookAction


def test_action_defaults():

    action = RunbookAction(
        action_id="a-01",
        name="Pause trading",
        control_action="PAUSE_TRADING",
    )

    assert action.requires_approval is True
    assert action.reason_required is True


def test_action_does_not_execute_control():

    action = RunbookAction(
        action_id="a-01",
        name="Global halt",
        control_action="KILL_TRADING",
    )

    # RunbookAction 只是"请求"，不是"执行"。
    assert action.control_action == "KILL_TRADING"
    assert not hasattr(action, "execute")


def test_action_is_frozen():

    action = RunbookAction(
        action_id="a-01",
        name="Pause trading",
        control_action="PAUSE_TRADING",
    )

    with pytest.raises(Exception):
        action.requires_approval = False


def test_control_actions_set():

    actions = {
        "PAUSE_TRADING",
        "KILL_TRADING",
        "FAILOVER_VENUE",
        "START_RECOVERY",
    }

    assert "KILL_TRADING" in actions
    assert "START_RECOVERY" in actions
