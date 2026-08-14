"""Governance integration: real GovernanceEngine behind the Control Plane (Commit 29 Part 1.2 §4, §32-33).

These tests wire the actual governance engine (principals, roles,
permissions, policies) into the governed pipeline and verify the three
authorization outcomes end-to-end.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from services.control_plane.authorizer import GovernanceAuthorizer
from services.control_plane.command import ControlCommand
from services.control_plane.dispatcher import ControlDispatcher
from services.control_plane.executor import ControlExecutor
from services.control_plane.pipeline import ControlPipeline
from services.control_plane.registry import ControlRegistry
from services.control_plane.request import ControlRequest
from services.control_plane.result import ControlResult
from services.control_plane.target import ControlTarget
from services.governance.decision import GovernanceEngine
from services.governance.models import Principal
from services.governance.registry import register_standard_governance, GovernanceRegistry


def _build_registry() -> GovernanceRegistry:
    registry = GovernanceRegistry()
    register_standard_governance(registry)
    registry.register_principal(
        Principal("ops-001", "Ops One", "human", active=True)
    )
    registry.register_principal(
        Principal("viewer-001", "Viewer", "human", active=True)
    )
    registry.register_principal(
        Principal("retired-001", "Retired One", "human", active=False)
    )
    return registry


def _roles_for(principal_id: str) -> tuple[str, ...]:
    return {
        "ops-001": ("CONTROL_OPERATOR",),
        "viewer-001": ("OBSERVER",),
        "retired-001": ("CONTROL_OPERATOR",),
    }.get(principal_id, ())


class _EchoHandler:
    def __init__(self):
        self.calls: list[ControlCommand] = []

    def execute(self, command: ControlCommand) -> ControlResult:
        self.calls.append(command)
        return ControlResult(
            command_id=command.command_id,
            state="SUCCEEDED",
            success=True,
            result={"action": command.action},
        )


@pytest.fixture
def pipeline():
    governance = GovernanceEngine(registry=_build_registry())
    authorizer = GovernanceAuthorizer(
        governance, role_resolver=_roles_for
    )

    registry = ControlRegistry()
    handler = _EchoHandler()
    registry.register("trading", "pause", handler)
    registry.register("trading", "kill", handler)
    registry.register("trading", "resume", handler)

    return (
        ControlPipeline(
            authorizer,
            ControlDispatcher(registry),
            ControlExecutor(),
        ),
        handler,
    )


@pytest.fixture
def make_request():
    def _make(**overrides):
        base = dict(
            request_id="REQ-INT-001",
            command=None,
            idempotency_key="IDEMP-INT-001",
            source="integration",
            submitted_at=datetime.now(timezone.utc),
        )
        base.update(overrides)
        return ControlRequest(**base)

    return _make


@pytest.fixture
def make_command():
    def _make(**overrides):
        base = dict(
            command_id="CMD-INT-001",
            command_type="TRADING",
            resource="trading",
            action="pause",
            requested_by="ops-001",
            parameters={"severity": "normal"},
            target=ControlTarget(
                service="oms", instance="oms-primary", environment="production"
            ),
            correlation_id="CORR-INT-001",
        )
        base.update(overrides)
        return ControlCommand(**base)

    return _make


class TestGovernanceIntegration:
    def test_production_pause_is_allowed(self, pipeline, make_request, make_command):
        control_pipeline, handler = pipeline
        result = control_pipeline.process(
            make_request(command=make_command())
        )
        assert result.state == "SUCCEEDED"
        assert result.success is True
        assert len(handler.calls) == 1

    def test_non_production_pause_is_denied(
        self, pipeline, make_request, make_command
    ):
        control_pipeline, handler = pipeline
        command = make_command(
            target=ControlTarget(
                service="oms", instance="oms-primary", environment="staging"
            )
        )
        result = control_pipeline.process(make_request(command=command))
        assert result.state == "REJECTED"
        assert result.success is False
        assert handler.calls == []

    def test_principal_without_permission_is_denied(
        self, pipeline, make_request, make_command
    ):
        control_pipeline, handler = pipeline
        command = make_command(requested_by="viewer-001")
        result = control_pipeline.process(make_request(command=command))
        assert result.state == "REJECTED"
        assert handler.calls == []

    def test_critical_pause_requires_approval(
        self, pipeline, make_request, make_command
    ):
        control_pipeline, handler = pipeline
        command = make_command(parameters={"severity": "CRITICAL"})
        result = control_pipeline.process(make_request(command=command))
        assert result.state == "WAITING_APPROVAL"
        assert result.success is False
        assert result.error_code in (
            "GOV_APPROVAL_REQUIRED",
            "APPROVAL_REQUIRED",
        )
        assert handler.calls == []

    def test_emergency_kill_is_allowed(self, pipeline, make_request, make_command):
        control_pipeline, handler = pipeline
        command = make_command(
            command_id="CMD-INT-KILL",
            action="kill",
            parameters={"severity": "EMERGENCY"},
        )
        result = control_pipeline.process(make_request(command=command))
        assert result.state == "SUCCEEDED"
        assert handler.calls == [command]

    def test_unknown_principal_is_denied(self, pipeline, make_request, make_command):
        control_pipeline, handler = pipeline
        command = make_command(requested_by="ghost-001")
        result = control_pipeline.process(make_request(command=command))
        assert result.state == "REJECTED"
        assert handler.calls == []

    def test_inactive_principal_is_denied(
        self, pipeline, make_request, make_command
    ):
        control_pipeline, handler = pipeline
        command = make_command(requested_by="retired-001")
        result = control_pipeline.process(make_request(command=command))
        assert result.state == "REJECTED"
        assert handler.calls == []
