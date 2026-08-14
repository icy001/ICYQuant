"""Authorization denied path through the ControlService (Commit 29 Part 1.2 §16, §27)."""

from __future__ import annotations

import pytest

from services.control_plane.audit import ControlAuditEventType, ControlAuditLog
from services.control_plane.authorizer import AuthorizationDecision
from services.control_plane.dispatcher import ControlDispatcher
from services.control_plane.executor import ControlExecutor
from services.control_plane.pipeline import ControlPipeline
from services.control_plane.registry import ControlRegistry
from services.control_plane.service import ControlService

from .conftest import FakeAuthorizer


def _build_service(decision: AuthorizationDecision, handler):
    authorizer = FakeAuthorizer(decision)
    registry = ControlRegistry()
    registry.register("trading", "pause", handler)
    dispatcher = ControlDispatcher(registry)
    executor = ControlExecutor()
    audit = ControlAuditLog()
    pipeline = ControlPipeline(
        authorizer,
        dispatcher,
        executor,
        audit_log=audit,
    )
    return ControlService(pipeline), authorizer, audit


class TestAuthorizationDenied:
    def test_governance_denial_blocks_execution(self, make_command, make_request, handler):
        service, _, audit = _build_service(AuthorizationDecision.deny(), handler)
        result = service.submit(make_request(make_command()))
        assert result.state == "REJECTED"
        assert result.success is False
        assert handler.calls == []

    def test_denial_never_reaches_the_dispatcher(
        self, make_command, make_request, handler
    ):
        service, _, _ = _build_service(AuthorizationDecision.deny(), handler)
        service.submit(make_request(make_command()))
        assert handler.calls == []

    def test_denial_records_denied_audit_with_correlation(
        self, make_command, make_request, handler
    ):
        service, _, audit = _build_service(AuthorizationDecision.deny(), handler)
        request = make_request(make_command())
        service.submit(request)
        types = [event.event_type for event in audit.events]
        assert types == [
            ControlAuditEventType.AUTHORIZATION_REQUESTED,
            ControlAuditEventType.AUTHORIZATION_DENIED,
        ]
        assert all(
            event.correlation_id == request.command.correlation_id
            for event in audit.events
        )

    def test_denied_result_carries_error_code(
        self, make_command, make_request, handler
    ):
        service, _, _ = _build_service(
            AuthorizationDecision.deny(reason_code="POLICY_DENIED"), handler
        )
        result = service.submit(make_request(make_command()))
        assert result.error_code == "POLICY_DENIED"

    def test_denial_is_not_an_execution_failure(self, make_command, make_request, handler):
        """DENY is a governance outcome, not an exception (§16)."""
        service, _, _ = _build_service(AuthorizationDecision.deny(), handler)
        result = service.submit(make_request(make_command()))
        assert result.error_code is not None
        assert result.state == "REJECTED"
