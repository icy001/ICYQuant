"""Tests for the strategy control command model."""

from __future__ import annotations

import dataclasses

import pytest

from services.strategy.control.commands import (
    KILL,
    PAUSE,
    RESUME,
    START,
    STOP,
    STRATEGY_CONTROL_ACTIONS,
    StrategyCommand,
    is_control_action,
)


def make_command(**overrides: object) -> StrategyCommand:
    defaults: dict[str, object] = {
        "command_id": "CMD-001",
        "strategy_id": "STRAT-001",
        "action": "pause",
        "principal_id": "operator-001",
        "parameters": {},
        "correlation_id": "CORR-001",
        "idempotency_key": "IDEMP-001",
    }
    defaults.update(overrides)
    return StrategyCommand(**defaults)


class TestControlActions:
    def test_action_constants(self) -> None:
        assert START == "start"
        assert PAUSE == "pause"
        assert RESUME == "resume"
        assert STOP == "stop"
        assert KILL == "kill"

    def test_control_actions_contains_all_five(self) -> None:
        assert STRATEGY_CONTROL_ACTIONS == {
            "start",
            "pause",
            "resume",
            "stop",
            "kill",
        }

    def test_is_control_action(self) -> None:
        for action in ("start", "pause", "resume", "stop", "kill"):
            assert is_control_action(action)

    def test_unknown_action_is_not_control(self) -> None:
        assert not is_control_action("restart")
        assert not is_control_action("destroy")


class TestStrategyCommand:
    def test_command_fields(self) -> None:
        command = make_command(parameters={"reason": "market halt"})
        assert command.command_id == "CMD-001"
        assert command.strategy_id == "STRAT-001"
        assert command.action == "pause"
        assert command.principal_id == "operator-001"
        assert command.parameters == {"reason": "market halt"}
        assert command.correlation_id == "CORR-001"
        assert command.idempotency_key == "IDEMP-001"

    def test_command_is_frozen(self) -> None:
        command = make_command()
        with pytest.raises(dataclasses.FrozenInstanceError):
            command.action = "stop"  # type: ignore[misc]

    def test_command_carries_idempotency_key(self) -> None:
        command = make_command(idempotency_key="IDEMP-KEY-9")
        assert command.idempotency_key == "IDEMP-KEY-9"
