"""Governance -> Control Plane end-to-end integration (Commit 29 Part 1.2 §32-33).

Written from the governance side: the full chain is

    Operator -> ControlService -> ControlPipeline -> GovernanceAuthorizer
             -> GovernanceEngine -> Dispatcher -> Handler -> Executor
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from services.control_plane.audit import (
    ControlAuditEventType,
    ControlAuditLog,
)
from services.control_plane.authorizer import GovernanceAuthorizer
from services.control_plane.command import ControlCommand
from services.control_plane.dispatcher import ControlDispatcher
from services.control_plane.executor import ControlExecutor
from services.control_plane.pipeline import ControlPipeline
from services.control_plane.registry import ControlRegistry
from services.control_plane.request import ControlRequest
from services.control_plane.result import ControlResult
from services.control_plane.service import ControlService
from services.control_plane.target import ControlTarget
from services.governance.decision import GovernanceEngine
from services.governance.models import Principal
from services.governance.registry import (
    GovernanceRegistry,
    register_standard_governance,
)


class _TradingHandler:
    def __init__(self):
        self.calls: list[ControlCommand] = []

    def execute(self, command: ControlCommand) -> ControlResult:
        self.calls.append(command)
        return ControlResult(
            command_id=command.command_id,
            state="SUCCEEDED",
            success=True,
            result={"controlled": f"{command.resource}:{command.action}"},
        )


@pytest.fixture
def stack():
    registry = GovernanceRegistry()
    register_standard_governance(registry)
    registry.register_principal(
        Principal("ops-001", "Ops One", "human", active=True)
    )

    engine = GovernanceEngine(registry=registry)
    authorizer = GovernanceAuthorizer(
        engine, role_resolver=lambda pid: ("CONTROL_OPERATOR",)
    )

    control_registry = ControlRegistry()
    handler = _TradingHandler()
    control_registry.register("trading", "pause", handler)
    control_registry.register("trading", "kill", handler)
    control_registry.register("trading", "resume", handler)

    audit = ControlAuditLog()
    pipeline = ControlPipeline(
        authorizer,
        ControlDispatcher(control_registry),
        ControlExecutor(),
        audit_log=audit,
    )
    service = ControlService(pipeline)
    return service, handler, audit


def _command(**overrides):
    base = dict(
        command_id="CMD-E2E-001",
        command_type="TRADING",
        resource="trading",
        action="pause",
        requested_by="ops-001",
        parameters={"severity": "normal"},
        target=ControlTarget(
            service="oms", instance="oms-primary", environment="production"
        ),
        correlation_id="CORR-E2E-001",
    )
    base.update(overrides)
    return ControlCommand(**base)


def _request(command, **overrides):
    base = dict(
        request_id="REQ-E2E-001",
        command=command,
        idempotency_key="IDEMP-E2E-001",
        source="governance-test",
        submitted_at=datetime.now(timezone.utc),
    )
    base.update(overrides)
    return ControlRequest(**base)


class TestEndToEnd:
    def test_allow_chain_reaches_target_service(self, stack):
        service, handler, _ = stack
        result = service.submit(_request(_command()))
        assert result.state == "SUCCEEDED"
        assert result.success is True
        assert len(handler.calls) == 1
        assert handler.calls[0].action == "pause"

    def test_deny_chain_stops_at_governance(self, stack):
        service, handler, _ = stack
        command = _command(
            target=ControlTarget(
                service="oms", instance="oms-primary", environment="staging"
            )
        )
        result = service.submit(_request(command))
        assert result.state == "REJECTED"
        assert handler.calls == []

    def test_approval_chain_waits_before_executor(self, stack):
        service, handler, _ = stack
        command = _command(parameters={"severity": "CRITICAL"})
        result = service.submit(_request(command))
        assert result.state == "WAITING_APPROVAL"
        assert result.success is False
        assert handler.calls == []

    def test_full_audit_chain_shared_correlation_id(self, stack):
        service, _, audit = stack
        request = _request(_command())
        service.submit(request)
        types = [event.event_type for event in audit.events]
        assert types == [
            ControlAuditEventType.AUTHORIZATION_REQUESTED,
            ControlAuditEventType.AUTHORIZATION_GRANT_CREATED,
            ControlAuditEventType.AUTHORIZATION_GRANTED,
            ControlAuditEventType.EXECUTION_STARTED,
            ControlAuditEventType.EXECUTION_SUCCEEDED,
        ]
        assert all(
            event.correlation_id == "CORR-E2E-001" for event in audit.events
        )

    def test_denied_audit_chain_has_no_execution_events(self, stack):
        service, _, audit = stack
        command = _command(
            target=ControlTarget(
                service="oms", instance="oms-primary", environment="test"
            )
        )
        service.submit(_request(command))
        types = [event.event_type for event in audit.events]
        assert ControlAuditEventType.AUTHORIZATION_DENIED in types
        assert ControlAuditEventType.EXECUTION_STARTED not in types

    def test_three_layer_ids_are_distinct(self, stack):
        service, _, _ = stack
        request = _request(
            _command(
                command_id="CMD-E2E-002",
                correlation_id="CORR-E2E-002",
            ),
            request_id="REQ-E2E-002",
        )
        result = service.submit(request)
        assert result.state == "SUCCEEDED"
        assert request.request_id != request.command.command_id
        # request_id (governance) and command_id (control plane) stay separate (§7).

    def test_governance_and_control_plane_stay_decoupled(self, stack):
        """Governance decides "may it be done"; the control plane routes it (§33)."""
        service, handler, _ = stack
        command = _command(
            action="resume",
            parameters={"severity": "normal"},
        )
        result = service.submit(_request(command))
        # standard resume policy requires recovery/reconciliation evidence that
        # is absent here -> no policy matches -> fail closed (DENY, never executes)
        assert result.state == "REJECTED"
        assert handler.calls == []
