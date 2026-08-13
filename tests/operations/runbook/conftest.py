"""Shared fixtures for runbook tests (Commit 27 Part 1.5)."""

from datetime import datetime, timezone

import pytest

from services.operations import (
    Runbook,
    RunbookSeverity,
    RunbookStep,
    StepType,
)


@pytest.fixture
def clock():

    now = datetime(2026, 8, 13, 13, 0, 0, tzinfo=timezone.utc)

    return lambda: now


def _step(
    order,
    step_id,
    name,
    step_type,
    description,
    required=True,
):

    return RunbookStep(
        step_id=step_id,
        order=order,
        name=name,
        step_type=step_type,
        description=description,
        required=required,
    )


@pytest.fixture
def service_unhealthy_steps():

    return (
        _step(1, "svc-01", "Service health", StepType.CHECK, "Service health"),
        _step(2, "svc-02", "Error rate", StepType.CHECK, "Error rate"),
        _step(3, "svc-03", "Restart / Failover", StepType.ACTION, "Restart / Failover"),
        _step(4, "svc-04", "Stabilization", StepType.WAIT, "Stabilization"),
        _step(5, "svc-05", "Health recovery", StepType.VALIDATION, "Health recovery"),
        _step(6, "svc-06", "Trading safety", StepType.VALIDATION, "Trading safety"),
    )


@pytest.fixture
def runbook_meta():

    return Runbook(
        runbook_id="RB-TEST-001",
        name="Test Runbook",
        description="Test runbook",
        severity=RunbookSeverity.STANDARD,
        version="1.0.0",
    )


@pytest.fixture
def runbook_definition(runbook_meta, service_unhealthy_steps):

    from services.operations import RunbookDefinition

    return RunbookDefinition(
        runbook_id=runbook_meta.runbook_id,
        name=runbook_meta.name,
        description=runbook_meta.description,
        severity=runbook_meta.severity,
        version=runbook_meta.version,
        steps=service_unhealthy_steps,
    )
