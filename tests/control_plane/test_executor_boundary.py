"""Executor boundary: grant guard and defense in depth (Commit 29 Part 1.2 §20-23, §29-31)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from dataclasses import replace

import pytest

from services.control_plane.authorizer import AuthorizationGrant
from services.control_plane.command import command_fingerprint
from services.control_plane.errors import AuthorizationExpired, UnauthorizedControl
from services.control_plane.executor import ControlExecutor
from services.control_plane.target import ControlTarget


def _grant_for(command, **overrides):
    params = dict(
        grant_id="GRANT-001",
        decision_id="DEC-001",
        request_id="REQ-001",
        command_id=command.command_id,
        principal_id=command.requested_by,
        resource=command.resource,
        action=command.action,
        granted_at=datetime.now(timezone.utc),
        fingerprint=command_fingerprint(command),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    params.update(overrides)
    return AuthorizationGrant(**params)


class TestExecutorBoundary:
    def test_executor_without_grant_is_backwards_compatible(
        self, make_command, handler
    ):
        """Part 1.1 skeleton path: no grant, direct handler call (§17)."""
        executor = ControlExecutor()
        result = executor.execute(make_command(), handler)
        assert result.state == "SUCCEEDED"
        assert handler.calls == [make_command()]

    def test_executor_with_valid_grant_executes(self, make_command, handler):
        executor = ControlExecutor()
        command = make_command()
        result = executor.execute(command, handler, _grant_for(command))
        assert result.state == "SUCCEEDED"
        assert handler.calls == [command]

    def test_modified_command_cannot_execute(self, make_command, handler):
        executor = ControlExecutor()
        command = make_command()
        grant = _grant_for(command)
        modified = replace(command, action="kill")
        with pytest.raises(UnauthorizedControl):
            executor.execute(modified, handler, grant)
        assert handler.calls == []

    def test_target_mutation_cannot_execute(self, make_command, handler):
        executor = ControlExecutor()
        command = make_command()
        grant = _grant_for(command)
        modified = replace(
            command,
            target=ControlTarget(
                service="oms", instance="oms-secondary", environment="production"
            ),
        )
        with pytest.raises(UnauthorizedControl):
            executor.execute(modified, handler, grant)
        assert handler.calls == []

    def test_parameter_mutation_cannot_execute(self, make_command, handler):
        executor = ControlExecutor()
        command = make_command()
        grant = _grant_for(command)
        modified = replace(command, parameters={"severity": "EMERGENCY"})
        with pytest.raises(UnauthorizedControl):
            executor.execute(modified, handler, grant)

    def test_expired_grant_rejected(self, make_command, handler):
        executor = ControlExecutor()
        command = make_command()
        past = datetime.now(timezone.utc) - timedelta(minutes=5)
        grant = _grant_for(command, granted_at=past, expires_at=past)
        with pytest.raises(AuthorizationExpired):
            executor.execute(command, handler, grant)
        assert handler.calls == []

    def test_executor_does_not_judge_permissions(self, make_command, handler):
        """The executor never decides "who may act" — only the grant matters (§17)."""
        executor = ControlExecutor()
        command = make_command(requested_by="anyone")
        grant = _grant_for(command)
        result = executor.execute(command, handler, grant)
        assert result.success is True

    def test_executor_guard_is_a_separate_layer(
        self, make_command, make_request, handler
    ):
        """Defense in depth: guard survives even when the pipeline is bypassed (§21)."""
        executor = ControlExecutor()
        command = make_command()
        grant = _grant_for(command)
        handler.execute(command)  # direct call works (no guard here)
        with pytest.raises(UnauthorizedControl):
            executor.execute(replace(command, action="kill"), handler, grant)
