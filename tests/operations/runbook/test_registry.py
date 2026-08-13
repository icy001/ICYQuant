"""Runbook registry / standard runbooks tests (Commit 27 Part 1.5,
spec sections 14-15, 33)."""

import pytest

from services.operations import (
    RunbookDefinition,
    RunbookRegistry,
    RunbookSeverity,
    RunbookValidator,
    StepType,
    build_standard_runbooks,
    register_standard_runbooks,
)
@pytest.fixture
def valid_definition():

    from services.operations import RunbookStep

    return RunbookDefinition(
        runbook_id="RB-TEST-001",
        name="Test",
        description="Test",
        severity=RunbookSeverity.STANDARD,
        version="1.0.0",
        steps=(
            RunbookStep(
                step_id="s-01",
                order=1,
                name="Check",
                step_type=StepType.CHECK,
                description="Check",
            ),
            RunbookStep(
                step_id="s-02",
                order=2,
                name="Validate",
                step_type=StepType.VALIDATION,
                description="Validate",
            ),
        ),
    )


def test_register_and_get(valid_definition):

    registry = RunbookRegistry()

    registry.register(valid_definition)

    assert registry.get(
        "RB-TEST-001",
        "1.0.0",
    ) is valid_definition


def test_latest_returns_last_registered(valid_definition):

    registry = RunbookRegistry()

    registry.register(valid_definition)

    v2 = RunbookDefinition(
        runbook_id="RB-TEST-001",
        name="Test v2",
        description="Test v2",
        severity=RunbookSeverity.STANDARD,
        version="2.0.0",
        steps=valid_definition.steps,
    )

    registry.register(v2)

    latest = registry.latest("RB-TEST-001")

    assert latest.version == "2.0.0"
    assert registry.versions("RB-TEST-001") == ("1.0.0", "2.0.0")


def test_latest_missing_returns_none():

    registry = RunbookRegistry()

    assert registry.latest("RB-NOPE-001") is None


def test_version_lock_keeps_old_version(valid_definition):

    registry = RunbookRegistry()

    registry.register(valid_definition)

    v2 = RunbookDefinition(
        runbook_id="RB-TEST-001",
        name="Test v2",
        description="Test v2",
        severity=RunbookSeverity.STANDARD,
        version="2.0.0",
        steps=valid_definition.steps,
    )

    registry.register(v2)

    # spec section 33: 历史 Incident 锁定 v1.0.0，不随最新版本切换
    locked = registry.get("RB-TEST-001", "1.0.0")

    assert locked is valid_definition


def test_register_validates_invalid_runbook():

    registry = RunbookRegistry()

    invalid = RunbookDefinition(
        runbook_id="RB-BAD-001",
        name="Bad",
        description="Bad",
        severity=RunbookSeverity.STANDARD,
        version="1.0.0",
        steps=(),
    )

    with pytest.raises(ValueError):
        registry.register(invalid)


def test_standard_runbooks_are_valid():

    validator = RunbookValidator()

    for runbook in build_standard_runbooks():
        assert validator.validate(runbook) is True


def test_standard_runbook_ids():
    # spec section 15
    runbook_ids = {
        runbook.runbook_id
        for runbook in build_standard_runbooks()
    }

    assert runbook_ids == {
        "RB-SERVICE-001",
        "RB-EVENTBUS-001",
        "RB-RECON-001",
        "RB-VENUE-001",
        "RB-EXEC-001",
        "RB-RISK-001",
        "RB-RECOVERY-001",
        "RB-KILL-001",
    }


def test_reconciliation_runbook_is_critical():

    runbooks = {
        runbook.runbook_id: runbook
        for runbook in build_standard_runbooks()
    }

    recon = runbooks["RB-RECON-001"]

    assert recon.severity is RunbookSeverity.CRITICAL
    assert len(recon.steps) == 11
    assert recon.step("rc-05").step_type is StepType.ACTION
    assert recon.step("rc-11").step_type is StepType.APPROVAL


def test_kill_runbook_is_emergency():

    runbooks = {
        runbook.runbook_id: runbook
        for runbook in build_standard_runbooks()
    }

    kill = runbooks["RB-KILL-001"]

    assert kill.severity is RunbookSeverity.EMERGENCY

    types = {s.step_type for s in kill.steps}

    assert StepType.ACTION in types
    assert StepType.APPROVAL in types


def test_register_standard_runbooks():

    registry = register_standard_runbooks(
        RunbookRegistry()
    )

    assert len(registry.all()) == 8
    assert registry.get("RB-RECON-001", "1.0.0") is not None
