"""Approval required path (Commit 29 Part 1.2 §13-15, §17, §28)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from services.control_plane.audit import ControlAuditEventType, ControlAuditLog
from services.control_plane.authorizer import AuthorizationDecision, AuthorizationGrant
from services.control_plane.command import command_fingerprint
from services.control_plane.dispatcher import ControlDispatcher
from services.control_plane.executor import ControlExecutor
from services.control_plane.pipeline import ControlPipeline
from services.control_plane.registry import ControlRegistry
from services.control_plane.service import ControlService
from services.control_plane.state import (
    CONTROL_STATE_TRANSITIONS,
    ControlState,
    is_valid_transition,
)

from .conftest import FakeAuthorizer


def _build_service(decision: AuthorizationDecision, handler, audit=None):
    authorizer = FakeAuthorizer(decision)
    registry = ControlRegistry()
    registry.register("trading", "pause", handler)
    dispatcher = ControlDispatcher(registry)
    executor = ControlExecutor()
    pipeline = ControlPipeline(
        authorizer,
        dispatcher,
        executor,
        audit_log=audit if audit is not None else ControlAuditLog(),
    )
    return ControlService(pipeline)


class TestApprovalRequired:
    def test_approval_required_blocks_execution(
        self, make_command, make_request, handler
    ):
        service = _build_service(
            AuthorizationDecision.require_approval(), handler
        )
        result = service.submit(make_request(make_command()))
        assert result.state == "WAITING_APPROVAL"
        assert result.success is False
        assert result.error_code in (
            "GOV_APPROVAL_REQUIRED",
            "APPROVAL_REQUIRED",
        )
        assert handler.calls == []

    def test_approval_required_records_approval_audit(
        self, make_command, make_request, handler
    ):
        audit = ControlAuditLog()
        service = _build_service(
            AuthorizationDecision.require_approval(), handler, audit=audit
        )
        request = make_request(make_command())
        service.submit(request)
        types = [event.event_type for event in audit.events]
        assert types == [
            ControlAuditEventType.AUTHORIZATION_REQUESTED,
            ControlAuditEventType.APPROVAL_REQUIRED,
        ]
        assert ControlAuditEventType.EXECUTION_STARTED not in types

    def test_waiting_approval_is_not_terminal(self):
        assert ControlState.WAITING_APPROVAL in CONTROL_STATE_TRANSITIONS
        assert is_valid_transition(
            ControlState.AUTHORIZING, ControlState.WAITING_APPROVAL
        )
        assert is_valid_transition(
            ControlState.WAITING_APPROVAL, ControlState.AUTHORIZED
        )
        assert not is_valid_transition(
            ControlState.WAITING_APPROVAL, ControlState.EXECUTING
        )

    def test_approved_command_executes_via_grant(
        self, make_command, make_request, handler
    ):
        """Quorum met -> final decision -> grant -> control plane -> executor (§14-15)."""
        service = _build_service(
            AuthorizationDecision.require_approval(), handler
        )
        request = make_request(make_command())
        pending = service.submit(request)
        assert pending.state == "WAITING_APPROVAL"
        assert handler.calls == []

        grant = AuthorizationGrant(
            grant_id="GRANT-APPROVED-001",
            decision_id="DEC-APPROVED-001",
            request_id=request.request_id,
            command_id=request.command.command_id,
            principal_id=request.command.requested_by,
            resource=request.command.resource,
            action=request.command.action,
            granted_at=datetime.now(timezone.utc),
            fingerprint=command_fingerprint(request.command),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        )
        result = service.submit_with_grant(request, grant)
        assert result.state == "SUCCEEDED"
        assert result.success is True
        assert handler.calls == [request.command]
