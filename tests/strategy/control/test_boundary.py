"""Tests for the strategy control boundary."""

from __future__ import annotations

import pytest

from services.strategy.control.boundary import StrategyControlBoundary
from services.strategy.control.commands import StrategyCommand
from services.strategy.control.result import StrategyControlResult
from services.strategy.control.validator import StrategyControlValidator


class FakeDispatcher:
    """Records commands submitted through the boundary."""

    def __init__(self) -> None:
        self.calls: list[StrategyCommand] = []

    def dispatch(self, command: StrategyCommand) -> str:
        self.calls.append(command)
        return "dispatched"

    @property
    def called_once(self) -> bool:
        return len(self.calls) == 1


class FakeRuntime:
    """A runtime that the boundary must never touch directly."""

    def __init__(self) -> None:
        self.executed = False

    def execute(self) -> None:
        self.executed = True


def make_command(action: str = "pause", **overrides: object) -> StrategyCommand:
    defaults: dict[str, object] = {
        "command_id": "CMD-001",
        "strategy_id": "STRAT-001",
        "action": action,
        "principal_id": "operator-001",
        "parameters": {},
        "correlation_id": "CORR-001",
        "idempotency_key": "IDEMP-001",
    }
    defaults.update(overrides)
    return StrategyCommand(**defaults)


def make_boundary(dispatcher: FakeDispatcher | None = None) -> StrategyControlBoundary:
    return StrategyControlBoundary(
        validator=StrategyControlValidator(),
        command_dispatcher=dispatcher or FakeDispatcher(),
    )


class TestBoundaryDispatchesValidCommands:
    def test_boundary_dispatches_valid_command(self) -> None:
        dispatcher = FakeDispatcher()
        boundary = make_boundary(dispatcher)

        command = make_command(action="pause")
        boundary.submit(command, "RUNNING")

        assert dispatcher.called_once
        assert dispatcher.calls[0] is command

    def test_boundary_does_not_execute_runtime(self) -> None:
        runtime = FakeRuntime()
        dispatcher = FakeDispatcher()
        boundary = make_boundary(dispatcher)

        command = make_command(action="pause")
        boundary.submit(command, "RUNNING")

        assert not runtime.executed

    def test_boundary_dispatches_kill_from_stopped(self) -> None:
        dispatcher = FakeDispatcher()
        boundary = make_boundary(dispatcher)

        boundary.submit(make_command(action="kill"), "STOPPED")

        assert dispatcher.called_once


class TestBoundaryRejectsIllegalCommands:
    def test_illegal_transition_is_rejected_before_dispatch(self) -> None:
        dispatcher = FakeDispatcher()
        boundary = make_boundary(dispatcher)

        with pytest.raises(ValueError):
            boundary.submit(make_command(action="pause"), "STOPPED")

        assert not dispatcher.calls

    def test_killed_strategy_cannot_resume(self) -> None:
        dispatcher = FakeDispatcher()
        boundary = make_boundary(dispatcher)

        with pytest.raises(ValueError):
            boundary.submit(make_command(action="resume"), "KILLED")

        assert not dispatcher.calls


class TestBoundaryResult:
    def test_pause_accepted_returns_pausing(self) -> None:
        dispatcher = FakeDispatcher()
        boundary = make_boundary(dispatcher)

        result = boundary.submit(make_command(action="pause"), "RUNNING")

        assert isinstance(result, StrategyControlResult)
        assert result.accepted is True
        assert result.previous_state == "RUNNING"
        assert result.current_state == "PAUSING"
        assert result.action == "pause"
        assert result.command_id == "CMD-001"
        assert result.strategy_id == "STRAT-001"

    def test_resume_accepted_returns_resuming(self) -> None:
        boundary = make_boundary()

        result = boundary.submit(make_command(action="resume"), "PAUSED")

        assert result.accepted is True
        assert result.current_state == "RESUMING"

    def test_stop_accepted_returns_stopping(self) -> None:
        boundary = make_boundary()

        result = boundary.submit(make_command(action="stop"), "RUNNING")

        assert result.accepted is True
        assert result.current_state == "STOPPING"

    def test_kill_accepted_returns_killed(self) -> None:
        boundary = make_boundary()

        result = boundary.submit(make_command(action="kill"), "RUNNING")

        assert result.accepted is True
        assert result.current_state == "KILLED"

    def test_start_accepted_returns_starting(self) -> None:
        boundary = make_boundary()

        result = boundary.submit(make_command(action="start"), "STOPPED")

        assert result.accepted is True
        assert result.current_state == "STARTING"

    def test_result_carries_command_identity(self) -> None:
        boundary = make_boundary()

        result = boundary.submit(
            make_command(command_id="CMD-777", strategy_id="STRAT-9", action="pause"),
            "RUNNING",
        )

        assert result.command_id == "CMD-777"
        assert result.strategy_id == "STRAT-9"
