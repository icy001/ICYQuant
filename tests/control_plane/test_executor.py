"""Executor boundary tests (Commit 29 Part 1.1 §17, §19).

The executor never decides whether an operation is permitted; it only runs
already-authorised commands through the registered handler. It contains no
``if action == "pause"`` branches — that would be a God Service.
"""

from datetime import datetime, timezone

from services.control_plane.command import ControlCommand
from services.control_plane.executor import ControlExecutor
from services.control_plane.result import ControlResult
from services.control_plane.target import ControlTarget

NOW = datetime(2026, 8, 13, 10, 0, 0, tzinfo=timezone.utc)


def make_command(action="pause"):
    return ControlCommand(
        command_id="CMD-001",
        resource="trading",
        action=action,
        requested_by="ops-001",
        target=ControlTarget(service="oms", instance="oms-primary"),
        created_at=NOW,
    )


class _RecordingHandler:
    def __init__(self, result=None):
        self.calls = []
        self.result = result or ControlResult(
            command_id="CMD-001", success=True
        )

    def execute(self, command):
        self.calls.append(command)
        return self.result


class TestControlExecutor:

    def test_executor_calls_handler_execute(self):
        handler = _RecordingHandler()
        command = make_command()
        ControlExecutor().execute(command, handler)
        assert handler.calls == [command]

    def test_executor_returns_handler_result(self):
        result = ControlResult(
            command_id="CMD-001",
            state="SUCCEEDED",
            success=True,
            result={"trading": "paused"},
        )
        handler = _RecordingHandler(result)
        returned = ControlExecutor().execute(make_command(), handler)
        assert returned is result

    def test_executor_does_not_decide_permission(self):
        """§17 — authorisation is decided elsewhere; the executor just runs."""
        executed = []

        class Handler:
            def execute(self, command):
                executed.append(command.action)
                return ControlResult(command_id=command.command_id)

        ControlExecutor().execute(make_command(action="kill"), Handler())
        assert executed == ["kill"]

    def test_executor_invokes_different_handlers_identically(self):
        """Every handler goes through the same unified interface (§20)."""

        class PauseHandler:
            def execute(self, command):
                return ControlResult(
                    command_id=command.command_id, success=True
                )

        class KillHandler:
            def execute(self, command):
                return ControlResult(
                    command_id=command.command_id,
                    state="FAILED",
                    success=False,
                    error_code="KILL_FAILED",
                )

        executor = ControlExecutor()
        paused = executor.execute(make_command(action="pause"), PauseHandler())
        killed = executor.execute(make_command(action="kill"), KillHandler())
        assert paused.success is True
        assert killed.success is False
        assert killed.error_code == "KILL_FAILED"
