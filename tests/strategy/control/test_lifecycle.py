"""Tests for strategy command arbitration."""

from __future__ import annotations

import pytest

from services.strategy.control.commands import StrategyCommand
from services.strategy.control.lifecycle import (
    CONTROL_PRIORITY,
    StrategyCommandArbiter,
)


def make_command(action: str, command_id: str = "CMD-001") -> StrategyCommand:
    return StrategyCommand(
        command_id=command_id,
        strategy_id="STRAT-001",
        action=action,
        principal_id="operator-001",
        parameters={},
        correlation_id="CORR-001",
        idempotency_key=f"IDEMP-{command_id}",
    )


class TestControlPriority:
    def test_kill_has_highest_priority(self) -> None:
        assert CONTROL_PRIORITY["kill"] == 100
        assert CONTROL_PRIORITY["kill"] > CONTROL_PRIORITY["stop"]
        assert CONTROL_PRIORITY["stop"] > CONTROL_PRIORITY["pause"]
        assert CONTROL_PRIORITY["pause"] > CONTROL_PRIORITY["resume"]
        assert CONTROL_PRIORITY["resume"] > CONTROL_PRIORITY["start"]

    def test_priority_values_match_spec(self) -> None:
        assert CONTROL_PRIORITY == {
            "start": 10,
            "resume": 20,
            "pause": 30,
            "stop": 40,
            "kill": 100,
        }


class TestStrategyCommandArbiter:
    def setup_method(self) -> None:
        self.arbiter = StrategyCommandArbiter()

    def test_kill_has_highest_priority(self) -> None:
        pause_command = make_command(action="pause", command_id="CMD-1")
        stop_command = make_command(action="stop", command_id="CMD-2")
        kill_command = make_command(action="kill", command_id="CMD-3")

        selected = self.arbiter.select(
            [pause_command, stop_command, kill_command]
        )

        assert selected.action == "kill"
        assert selected is kill_command

    def test_select_returns_only_command(self) -> None:
        command = make_command(action="pause")
        assert self.arbiter.select([command]) is command

    def test_pause_beats_stop_when_no_kill(self) -> None:
        pause_command = make_command(action="pause", command_id="CMD-1")
        stop_command = make_command(action="stop", command_id="CMD-2")

        selected = self.arbiter.select([pause_command, stop_command])

        assert selected.action == "stop"

    def test_empty_commands_raise(self) -> None:
        with pytest.raises(ValueError):
            self.arbiter.select([])

    def test_unknown_action_raises(self) -> None:
        with pytest.raises(ValueError):
            self.arbiter.select(
                [make_command(action="pause"), make_command(action="nuke")]
            )
