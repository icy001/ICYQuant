"""Control pipeline: governed authorization flow (Commit 29 Part 1.2 §6-17)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from services.control_plane.audit import ControlAuditEventType
from services.control_plane.authorizer import (
    AuthorizationGrant,
    GovernanceAuthorizer,
)
from services.control_plane.command import command_fingerprint
from services.control_plane.dispatcher import ControlDispatcher
from services.control_plane.errors import (
    AuthorizationExpired,
    CommandConflict,
    CommandNotFound,
    UnauthorizedControl,
)
from services.control_plane.executor import ControlExecutor
from services.control_plane.pipeline import ControlPipeline
from services.control_plane.registry import ControlRegistry, IdempotencyRegistry
from services.governance.decision import (
    DecisionEffect,
    GovernanceContext,
    GovernanceDecision,
)


class FakeGovernance:
    """Governance stand-in that can produce any effect per call."""

    def __init__(self, *decisions):
        self._decisions = list(decisions) or [
            GovernanceDecision(effect=DecisionEffect.ALLOW, reason="allowed")
        ]
        self.contexts: list[GovernanceContext] = []

    def evaluate(self, context: GovernanceContext) -> GovernanceDecision:
        self.contexts.append(context)
        decision = self._decisions.pop(0)
        return decision


def _build_pipeline(
    *,
    governance=None,
    audit_log=None,
    idempotency=None,
    register_handler=True,
    executor=None,
    handler=None,
):
    registry = ControlRegistry()
    if register_handler:
        target = handler or (lambda command: None)
        registry.register("trading", "pause", _HandlerAdapter(target))
        registry.register("trading", "kill", _HandlerAdapter(target))
    dispatcher = ControlDispatcher(registry)
    executor = executor or ControlExecutor()
    authorizer = GovernanceAuthorizer(governance or FakeGovernance())
    return ControlPipeline(
        authorizer,
        dispatcher,
        executor,
        audit_log=audit_log,
        idempotency=idempotency,
    )


class _HandlerAdapter:
    def __init__(self, fn):
        self._fn = fn

    def execute(self, command):
        return self._fn(command)


class TestAllowPath:
    def test_allow_executes_handler_end_to_end(self, make_command, make_request, handler):
        pipeline = _build_pipeline(handler=handler.execute)
        result = pipeline.process(make_request(make_command()))
        assert result.state == "SUCCEEDED"
        assert result.success is True
        assert handler.calls == [make_command()]

    def test_allow_records_full_audit_chain(self, make_command, make_request, handler):
        from services.control_plane.audit import ControlAuditLog

        audit = ControlAuditLog()
        pipeline = _build_pipeline(handler=handler.execute, audit_log=audit)
        request = make_request(make_command())
        pipeline.process(request)
        types = [event.event_type for event in audit.events]
        assert types == [
            ControlAuditEventType.AUTHORIZATION_REQUESTED,
            ControlAuditEventType.AUTHORIZATION_GRANT_CREATED,
            ControlAuditEventType.AUTHORIZATION_GRANTED,
            ControlAuditEventType.EXECUTION_STARTED,
            ControlAuditEventType.EXECUTION_SUCCEEDED,
        ]
        assert all(
            event.correlation_id == request.command.correlation_id
            for event in audit.events
        )

    def test_allow_produces_grant_and_executor_guard_passes(
        self, make_command, make_request, handler
    ):
        seen = {}

        def spy(command, inner_grant):
            seen["grant"] = inner_grant
            return handler.execute(command)

        class SpyExecutor:
            def __init__(self):
                self.calls = []

            def execute(self, command, h, grant=None):
                self.calls.append((command, h, grant))
                seen["grant"] = grant
                return h.execute(command)

        spy_executor = SpyExecutor()
        pipeline = _build_pipeline(executor=spy_executor, handler=handler.execute)
        request = make_request(make_command())
        result = pipeline.process(request)
        assert result.success
        assert seen["grant"] is not None
        assert seen["grant"].command_id == "CMD-001"
        assert seen["grant"].fingerprint == command_fingerprint(request.command)


class TestDenyPath:
    def test_deny_never_reaches_dispatcher(self, make_command, make_request, handler):
        governance = FakeGovernance(
            GovernanceDecision(effect=DecisionEffect.DENY, reason="blocked")
        )
        pipeline = _build_pipeline(governance=governance, handler=handler.execute)
        result = pipeline.process(make_request(make_command()))
        assert result.state == "REJECTED"
        assert result.success is False
        assert result.error_code in ("GOV_DENIED", "GOVERNANCE_DENIED")
        assert handler.calls == []

    def test_deny_records_denial_audit(self, make_command, make_request, handler):
        from services.control_plane.audit import ControlAuditLog

        audit = ControlAuditLog()
        governance = FakeGovernance(
            GovernanceDecision(effect=DecisionEffect.DENY, reason="blocked")
        )
        pipeline = _build_pipeline(
            governance=governance, handler=handler.execute, audit_log=audit
        )
        pipeline.process(make_request(make_command()))
        types = [event.event_type for event in audit.events]
        assert ControlAuditEventType.AUTHORIZATION_DENIED in types
        assert ControlAuditEventType.EXECUTION_STARTED not in types


class TestApprovalGate:
    def test_require_approval_never_reaches_executor(
        self, make_command, make_request, handler
    ):
        governance = FakeGovernance(
            GovernanceDecision(
                effect=DecisionEffect.REQUIRE_APPROVAL, reason="approve me"
            )
        )
        pipeline = _build_pipeline(governance=governance, handler=handler.execute)
        result = pipeline.process(make_request(make_command()))
        assert result.state == "WAITING_APPROVAL"
        assert result.success is False
        assert result.error_code in ("GOV_APPROVAL_REQUIRED", "APPROVAL_REQUIRED")
        assert handler.calls == []

    def test_require_approval_records_approval_audit(
        self, make_command, make_request, handler
    ):
        from services.control_plane.audit import ControlAuditLog

        audit = ControlAuditLog()
        governance = FakeGovernance(
            GovernanceDecision(
                effect=DecisionEffect.REQUIRE_APPROVAL, reason="approve me"
            )
        )
        pipeline = _build_pipeline(
            governance=governance, handler=handler.execute, audit_log=audit
        )
        pipeline.process(make_request(make_command()))
        types = [event.event_type for event in audit.events]
        assert ControlAuditEventType.APPROVAL_REQUIRED in types
        assert ControlAuditEventType.EXECUTION_STARTED not in types


class TestIdempotency:
    def test_resubmission_returns_previous_result(self, make_command, make_request, handler):
        idempotency = IdempotencyRegistry()
        pipeline = _build_pipeline(
            handler=handler.execute, idempotency=idempotency
        )
        request = make_request(make_command())
        first = pipeline.process(request)
        second = pipeline.process(request)
        assert first == second
        assert len(handler.calls) == 1

    def test_idempotency_conflict_is_rejected(self, make_command, make_request, handler):
        idempotency = IdempotencyRegistry()
        pipeline = _build_pipeline(
            handler=handler.execute, idempotency=idempotency
        )
        pause = make_request(make_command())
        kill = make_request(
            make_command(command_id="CMD-002", action="kill"),
            idempotency_key=pause.idempotency_key,
        )
        pipeline.process(pause)
        with pytest.raises(CommandConflict):
            pipeline.process(kill)


class TestSubmitWithGrant:
    def test_approved_command_executes(self, make_command, make_request, handler):
        pipeline = _build_pipeline(handler=handler.execute)
        request = make_request(make_command())
        grant = AuthorizationGrant(
            grant_id="GRANT-APPROVED",
            decision_id="DEC-APPROVED",
            request_id=request.request_id,
            command_id=request.command.command_id,
            principal_id=request.command.requested_by,
            resource=request.command.resource,
            action=request.command.action,
            granted_at=datetime.now(timezone.utc),
            fingerprint=command_fingerprint(request.command),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        )
        result = pipeline.submit_with_grant(request, grant)
        assert result.state == "SUCCEEDED"
        assert handler.calls == [request.command]

    def test_invalid_grant_is_rejected(self, make_command, make_request, handler):
        from dataclasses import replace

        pipeline = _build_pipeline(handler=handler.execute)
        command = make_command()
        request = make_request(command)
        grant = AuthorizationGrant(
            grant_id="GRANT-BAD",
            decision_id="DEC-BAD",
            request_id=request.request_id,
            command_id=command.command_id,
            principal_id=command.requested_by,
            resource=command.resource,
            action=command.action,
            granted_at=datetime.now(timezone.utc),
            fingerprint=command_fingerprint(replace(command, action="kill")),
        )
        with pytest.raises(UnauthorizedControl):
            pipeline.submit_with_grant(request, grant)
        assert handler.calls == []

    def test_expired_grant_is_rejected(self, make_command, make_request, handler):
        pipeline = _build_pipeline(handler=handler.execute)
        request = make_request(make_command())
        past = datetime.now(timezone.utc) - timedelta(minutes=5)
        grant = AuthorizationGrant(
            grant_id="GRANT-EXPIRED",
            decision_id="DEC-EXPIRED",
            request_id=request.request_id,
            command_id=request.command.command_id,
            principal_id=request.command.requested_by,
            resource=request.command.resource,
            action=request.command.action,
            granted_at=past,
            fingerprint=command_fingerprint(request.command),
            expires_at=past,
        )
        with pytest.raises(AuthorizationExpired):
            pipeline.submit_with_grant(request, grant)
        assert handler.calls == []


class TestFailClosed:
    def test_unknown_command_rejected_after_authorization(
        self, make_command, make_request
    ):
        registry = ControlRegistry()
        dispatcher = ControlDispatcher(registry)
        pipeline = ControlPipeline(
            GovernanceAuthorizer(FakeGovernance()),
            dispatcher,
            ControlExecutor(),
        )
        command = make_command(resource="unknown", action="destroy")
        with pytest.raises(CommandNotFound):
            pipeline.process(make_request(command))

    def test_invalid_request_rejected_before_authorization(
        self, make_command, make_request
    ):
        from services.control_plane.errors import InvalidControlRequest

        pipeline = _build_pipeline()
        request = make_request(make_command(), request_id="")
        with pytest.raises(InvalidControlRequest):
            pipeline.process(request)
