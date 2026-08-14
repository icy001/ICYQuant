"""Shared fixtures for the control plane tests (Commit 29 Part 1.2 / Part 1.3)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from services.control_plane.authorizer import AuthorizationDecision
from services.control_plane.command import ControlCommand
from services.control_plane.execution_attempt import ExecutionAttempt, ExecutionState
from services.control_plane.request import ControlRequest
from services.control_plane.result import ControlResult
from services.control_plane.store import CommandRecord
from services.control_plane.target import ControlTarget


class RecordingHandler:
    """Handlers that records every command it executed."""

    def __init__(self) -> None:
        self.calls: list[ControlCommand] = []

    def execute(self, command: ControlCommand) -> ControlResult:
        self.calls.append(command)
        return ControlResult(
            command_id=command.command_id,
            state="SUCCEEDED",
            success=True,
            result={"handled": command.action},
        )


class FakeAuthorizer:
    """Configurable ControlAuthorizer returning a fixed decision."""

    def __init__(self, decision: AuthorizationDecision) -> None:
        self.decision = decision
        self.contexts = []

    def authorize(self, context):
        self.contexts.append(context)
        return self.decision


@pytest.fixture
def make_command():
    def _make(**overrides):
        base = dict(
            command_id="CMD-001",
            command_type="TRADING",
            resource="trading",
            action="pause",
            requested_by="ops-001",
            parameters={"severity": "normal"},
            target=ControlTarget(
                service="oms", instance="oms-primary", environment="production"
            ),
            correlation_id="CORR-20260813-001",
        )
        base.update(overrides)
        return ControlCommand(**base)

    return _make


@pytest.fixture
def make_request():
    def _make(command=None, **overrides):
        base = dict(
            request_id="REQ-001",
            command=command,
            idempotency_key="IDEMP-001",
            source="console",
            submitted_at=datetime.now(timezone.utc),
        )
        base.update(overrides)
        return ControlRequest(**base)

    return _make


@pytest.fixture
def handler():
    return RecordingHandler()


@pytest.fixture
def allow_authorizer():
    return FakeAuthorizer(AuthorizationDecision.allow())


@pytest.fixture
def deny_authorizer():
    return FakeAuthorizer(AuthorizationDecision.deny())


@pytest.fixture
def approval_authorizer():
    return FakeAuthorizer(AuthorizationDecision.require_approval())


class MutableCommand:
    """Duck-typed mutable command used by the lifecycle tests (§7).

    The durable lifecycle operates on mutable records; the frozen
    ``ControlCommand`` keeps its immutable ``with_state`` copy semantics.
    """

    def __init__(
        self,
        command_id: str = "CMD-001",
        resource: str = "trading",
        action: str = "pause",
        state: str = "RECEIVED",
    ) -> None:
        self.command_id = command_id
        self.resource = resource
        self.action = action
        self.state = state


@pytest.fixture
def mutable_command() -> MutableCommand:
    return MutableCommand()


@pytest.fixture
def make_record():
    def _make(**overrides):
        base = dict(
            command_id="CMD-001",
            request_id="REQ-001",
            state="RECEIVED",
            version=1,
            updated_at=datetime.now(timezone.utc),
            correlation_id="CORR-20260813-001",
            authorization_decision_id=None,
        )
        base.update(overrides)
        return CommandRecord(**base)

    return _make


@pytest.fixture
def make_attempt():
    def _make(**overrides):
        base = dict(
            attempt_id="ATTEMPT-001",
            command_id="CMD-001",
            attempt_number=1,
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
            state=ExecutionState.STARTED,
            error_code=None,
        )
        base.update(overrides)
        return ExecutionAttempt(**base)

    return _make
