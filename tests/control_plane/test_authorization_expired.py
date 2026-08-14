"""Authorization expiration (Commit 29 Part 1.2 §12, §30)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from services.control_plane.authorizer import AuthorizationGrant
from services.control_plane.command import command_fingerprint
from services.control_plane.dispatcher import ControlDispatcher
from services.control_plane.errors import (
    AuthorizationExpired,
    UnauthorizedControl,
)
from services.control_plane.executor import ControlExecutor
from services.control_plane.pipeline import ControlPipeline
from services.control_plane.registry import ControlRegistry
from services.control_plane.service import ControlService

from .conftest import FakeAuthorizer


def _expired_grant(request):
    past = datetime.now(timezone.utc) - timedelta(minutes=10)
    return AuthorizationGrant(
        grant_id="GRANT-EXPIRED",
        decision_id="DEC-001",
        request_id=request.request_id,
        command_id=request.command.command_id,
        principal_id=request.command.requested_by,
        resource=request.command.resource,
        action=request.command.action,
        granted_at=past,
        fingerprint=command_fingerprint(request.command),
        expires_at=past,
    )


def _valid_grant(request):
    now = datetime.now(timezone.utc)
    return AuthorizationGrant(
        grant_id="GRANT-VALID",
        decision_id="DEC-001",
        request_id=request.request_id,
        command_id=request.command.command_id,
        principal_id=request.command.requested_by,
        resource=request.command.resource,
        action=request.command.action,
        granted_at=now,
        fingerprint=command_fingerprint(request.command),
        expires_at=now + timedelta(minutes=5),
    )


class TestAuthorizationExpired:
    def test_expired_grant_rejected_by_executor(self, make_command, make_request, handler):
        executor = ControlExecutor()
        request = make_request(make_command())
        with pytest.raises(AuthorizationExpired) as exc_info:
            executor.execute(request.command, handler, _expired_grant(request))
        assert isinstance(exc_info.value, UnauthorizedControl)
        assert handler.calls == []

    def test_expired_grant_rejected_by_pipeline(
        self, make_command, make_request, handler
    ):
        registry = ControlRegistry()
        registry.register("trading", "pause", handler)
        pipeline = ControlPipeline(
            FakeAuthorizer(_make_allow()),
            ControlDispatcher(registry),
            ControlExecutor(),
        )
        request = make_request(make_command())
        with pytest.raises(AuthorizationExpired):
            pipeline.submit_with_grant(request, _expired_grant(request))
        assert handler.calls == []

    def test_valid_grant_still_executes(self, make_command, make_request, handler):
        registry = ControlRegistry()
        registry.register("trading", "pause", handler)
        pipeline = ControlPipeline(
            FakeAuthorizer(_make_allow()),
            ControlDispatcher(registry),
            ControlExecutor(),
        )
        request = make_request(make_command())
        result = pipeline.submit_with_grant(request, _valid_grant(request))
        assert result.state == "SUCCEEDED"
        assert handler.calls == [request.command]


def _make_allow():
    from services.control_plane.authorizer import AuthorizationDecision

    return AuthorizationDecision.allow()
