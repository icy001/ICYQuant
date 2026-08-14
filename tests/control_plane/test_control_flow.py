"""End-to-end control plane flow tests (Commit 29 Part 1.1 §22-23, §27-30, §36, §39-41).

Exercises the ``ControlPlane.submit`` pipeline: validation -> target
resolution -> idempotency -> governance authorization boundary -> dispatch
-> registry -> handler -> executor, plus the command lifecycle state machine.
"""

from datetime import datetime, timezone

import pytest

from services.control_plane.command import ControlCommand
from services.control_plane.dispatcher import ControlDispatcher
from services.control_plane.errors import (
    CommandConflict,
    CommandNotFound,
    ControlExecutionError,
    InvalidControlRequest,
    InvalidControlState,
    TargetNotFound,
    UnauthorizedControl,
)
from services.control_plane.executor import ControlExecutor
from services.control_plane.models import ControlPlane
from services.control_plane.registry import ControlRegistry
from services.control_plane.request import ControlRequest
from services.control_plane.result import ControlResult
from services.control_plane.state import (
    CONTROL_STATE_TRANSITIONS,
    ControlState,
    is_valid_transition,
    validate_transition,
)
from services.control_plane.target import (
    ControlTarget,
    StaticTargetResolver,
)

NOW = datetime(2026, 8, 13, 10, 0, 0, tzinfo=timezone.utc)

PROD_OMS = ControlTarget(
    service="oms", instance="oms-primary", environment="production"
)


def make_command(resource="trading", action="pause", command_id="CMD-001"):
    return ControlCommand(
        command_id=command_id,
        resource=resource,
        action=action,
        requested_by="ops-001",
        target=PROD_OMS,
        created_at=NOW,
    )


def make_request(command, idempotency_key="IDEMP-001", request_id="REQ-001"):
    return ControlRequest(
        request_id=request_id,
        command=command,
        submitted_at=NOW,
        idempotency_key=idempotency_key,
        source="ops-console",
    )


class FakeHandler:
    def __init__(self, result=None, error=None, name=None):
        self.name = name or "handler"
        self.result = result
        self.error = error
        self.calls = []

    def execute(self, command):
        self.calls.append(command)
        if self.error is not None:
            raise self.error
        if self.result is not None:
            return self.result
        return ControlResult(
            command_id=command.command_id,
            state=ControlState.SUCCEEDED.value,
            success=True,
        )


class FakeAuthorizer:
    def __init__(self, allow=True):
        self.allow = allow
        self.requests = []

    def authorize(self, request):
        self.requests.append(request)
        if not self.allow:
            raise UnauthorizedControl(
                f"governance rejected request {request.request_id}"
            )


def make_control_plane(
    authorizer=None,
    target_resolver=None,
    handlers=None,
    idempotency_registry=None,
):
    registry = ControlRegistry()
    for (resource, action), handler in (handlers or {}).items():
        registry.register(resource, action, handler)
    dispatcher = ControlDispatcher(registry)
    executor = ControlExecutor()
    return ControlPlane(
        registry,
        dispatcher,
        executor,
        authorizer=authorizer,
        target_resolver=target_resolver,
        idempotency_registry=idempotency_registry,
    )


class TestControlPlaneSubmit:

    def test_submit_success(self):
        handler = FakeHandler()
        plane = make_control_plane(
            handlers={("trading", "pause"): handler}
        )
        result = plane.submit(make_request(make_command()))
        assert result.success is True
        assert result.state == ControlState.SUCCEEDED.value
        assert result.command_id == "CMD-001"

    def test_submit_routes_through_registry(self):
        handler = FakeHandler(name="trading-pause")
        plane = make_control_plane(
            handlers={("trading", "pause"): handler}
        )
        plane.submit(make_request(make_command()))
        assert handler.calls == [make_command()]

    def test_command_starts_received(self):
        """§36 — the command begins its lifecycle in RECEIVED."""
        assert make_command().state == ControlState.RECEIVED

    def test_idempotent_control(self):
        """§39 — resubmitting the same request returns the previous result."""
        handler = FakeHandler()
        plane = make_control_plane(
            handlers={("trading", "pause"): handler}
        )
        request = make_request(make_command())
        first = plane.submit(request)
        second = plane.submit(request)
        assert first == second
        # The handler ran exactly once — the second submit was served from
        # the idempotency registry.
        assert len(handler.calls) == 1

    def test_idempotency_conflict(self):
        """§40 — same idempotency key + different command fingerprint."""
        pause_handler = FakeHandler(name="pause")
        kill_handler = FakeHandler(name="kill")
        plane = make_control_plane(
            handlers={
                ("trading", "pause"): pause_handler,
                ("trading", "kill"): kill_handler,
            }
        )
        plane.submit(make_request(make_command(action="pause")))
        with pytest.raises(CommandConflict):
            plane.submit(make_request(make_command(action="kill")))

    def test_unknown_command_rejected(self):
        """§41 — unknown resource:action is rejected (fail closed)."""
        plane = make_control_plane(
            handlers={("trading", "pause"): FakeHandler()}
        )
        command = make_command(resource="unknown", action="destroy")
        with pytest.raises(CommandNotFound):
            plane.submit(make_request(command))

    def test_invalid_request_rejected(self):
        """§32 — a request missing critical fields never reaches the dispatcher."""
        handler = FakeHandler()
        plane = make_control_plane(
            handlers={("trading", "pause"): handler}
        )
        bad = make_request(make_command(), request_id="")
        with pytest.raises(InvalidControlRequest):
            plane.submit(bad)
        assert handler.calls == []

    def test_unauthorized_control_rejected(self):
        """§25 — Governance denial stops the pipeline before dispatch."""
        handler = FakeHandler()
        authorizer = FakeAuthorizer(allow=False)
        plane = make_control_plane(
            authorizer=authorizer,
            handlers={("trading", "pause"): handler},
        )
        request = make_request(make_command())
        with pytest.raises(UnauthorizedControl):
            plane.submit(request)
        assert authorizer.requests == [request]
        assert handler.calls == []

    def test_authorizer_observed_on_submit(self):
        handler = FakeHandler()
        authorizer = FakeAuthorizer(allow=True)
        plane = make_control_plane(
            authorizer=authorizer,
            handlers={("trading", "pause"): handler},
        )
        request = make_request(make_command())
        plane.submit(request)
        assert authorizer.requests == [request]
        assert len(handler.calls) == 1

    def test_target_not_found_fail_closed(self):
        """§34 — production + unknown instance is rejected before dispatch."""
        handler = FakeHandler()
        plane = make_control_plane(
            target_resolver=StaticTargetResolver(),
            handlers={("trading", "pause"): handler},
        )
        target = ControlTarget(
            service="oms", instance="test-oms", environment="production"
        )
        request = make_request(
            ControlCommand(
                command_id="CMD-002",
                resource="trading",
                action="pause",
                requested_by="ops-001",
                target=target,
                created_at=NOW,
            )
        )
        with pytest.raises(TargetNotFound):
            plane.submit(request)
        assert handler.calls == []

    def test_executor_failure_wrapped(self):
        """§17 — a handler crash surfaces as ControlExecutionError."""
        handler = FakeHandler(error=RuntimeError("oms unreachable"))
        plane = make_control_plane(
            handlers={("trading", "pause"): handler}
        )
        with pytest.raises(ControlExecutionError):
            plane.submit(make_request(make_command()))

    def test_failed_result_returns_normally(self):
        """A handler reporting failure returns a result; it does not crash."""

        class FailingHandler:
            def execute(self, command):
                return ControlResult(
                    command_id=command.command_id,
                    state=ControlState.FAILED.value,
                    success=False,
                    error_code="PAUSE_FAILED",
                    error_message="could not pause",
                )

        plane = make_control_plane(
            handlers={("trading", "pause"): FailingHandler()}
        )
        result = plane.submit(make_request(make_command()))
        assert result.success is False
        assert result.state == ControlState.FAILED.value
        assert result.error_code == "PAUSE_FAILED"

    def test_three_layer_ids_kept_separate(self):
        """§7 — Request ID / Decision ID / Command ID must not be merged."""
        handler = FakeHandler()
        plane = make_control_plane(
            handlers={("trading", "pause"): handler}
        )
        request = make_request(
            make_command(command_id="CMD-001"), request_id="REQ-001"
        )
        result = plane.submit(request)
        assert request.request_id == "REQ-001"
        assert request.command.command_id == "CMD-001"
        assert result.command_id == "CMD-001"
        assert request.request_id != result.command_id


class TestControlStateLifecycle:

    def test_valid_progression(self):
        states = [
            ControlState.RECEIVED,
            ControlState.AUTHORIZING,
            ControlState.AUTHORIZED,
            ControlState.DISPATCHING,
            ControlState.EXECUTING,
            ControlState.SUCCEEDED,
        ]
        for current, next_state in zip(states, states[1:]):
            assert is_valid_transition(current, next_state)
            validate_transition(current, next_state)

    def test_rejected_from_authorizing(self):
        validate_transition(ControlState.AUTHORIZING, ControlState.REJECTED)

    def test_failed_from_executing(self):
        validate_transition(ControlState.EXECUTING, ControlState.FAILED)

    def test_invalid_jump_rejected(self):
        """§15 — RECEIVED -> SUCCEEDED is not allowed."""
        with pytest.raises(InvalidControlState):
            validate_transition(ControlState.RECEIVED, ControlState.SUCCEEDED)

    def test_authorizing_to_succeeded_rejected(self):
        with pytest.raises(InvalidControlState):
            validate_transition(ControlState.AUTHORIZING, ControlState.SUCCEEDED)

    def test_terminal_states_have_no_outgoing(self):
        for terminal in (
            ControlState.SUCCEEDED,
            ControlState.FAILED,
            ControlState.REJECTED,
            ControlState.CANCELLED,
        ):
            assert CONTROL_STATE_TRANSITIONS[terminal] == frozenset()
