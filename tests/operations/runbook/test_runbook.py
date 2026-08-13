"""Runbook definition / validator tests (Commit 27 Part 1.5,
spec sections 34-35, 37)."""

import pytest

from services.operations import (
    Runbook,
    RunbookDefinition,
    RunbookSeverity,
    RunbookStep,
    RunbookValidator,
    StepType,
)


def _step(order, step_id, step_type):
    return RunbookStep(
        step_id=step_id,
        order=order,
        name=step_id,
        step_type=step_type,
        description=step_id,
    )


def _valid_steps():
    return (
        _step(1, "s-01", StepType.CHECK),
        _step(2, "s-02", StepType.ACTION),
        _step(3, "s-03", StepType.VALIDATION),
    )


def test_runbook_requires_steps():
    # spec section 37
    validator = RunbookValidator()

    runbook = Runbook(
        runbook_id="RB-001",
        name="Test",
        description="Test",
        severity=RunbookSeverity.STANDARD,
        version="1.0.0",
    )

    with pytest.raises(ValueError):
        validator.validate(runbook, [])


def test_runbook_id_required():

    validator = RunbookValidator()

    runbook = Runbook(
        runbook_id="",
        name="Test",
        description="Test",
        severity=RunbookSeverity.STANDARD,
        version="1.0.0",
    )

    with pytest.raises(ValueError):
        validator.validate(runbook, _valid_steps())


def test_duplicate_step_order_rejected():

    validator = RunbookValidator()

    runbook = Runbook(
        runbook_id="RB-001",
        name="Test",
        description="Test",
        severity=RunbookSeverity.STANDARD,
        version="1.0.0",
    )

    steps = (
        _step(1, "s-01", StepType.CHECK),
        _step(1, "s-02", StepType.VALIDATION),
    )

    with pytest.raises(ValueError):
        validator.validate(runbook, steps)


def test_no_validation_rejected():
    # spec section 34
    validator = RunbookValidator()

    runbook = Runbook(
        runbook_id="RB-001",
        name="Test",
        description="Test",
        severity=RunbookSeverity.STANDARD,
        version="1.0.0",
    )

    steps = (
        _step(1, "s-01", StepType.CHECK),
        _step(2, "s-02", StepType.ACTION),
    )

    with pytest.raises(ValueError):
        validator.validate(runbook, steps)


def test_valid_runbook_passes():

    validator = RunbookValidator()

    runbook = Runbook(
        runbook_id="RB-001",
        name="Test",
        description="Test",
        severity=RunbookSeverity.STANDARD,
        version="1.0.0",
    )

    assert validator.validate(runbook, _valid_steps()) is True


def test_emergency_requires_approval_and_action():
    # spec section 34
    validator = RunbookValidator()

    runbook = Runbook(
        runbook_id="RB-KILL-001",
        name="Emergency",
        description="Emergency",
        severity=RunbookSeverity.EMERGENCY,
        version="1.0.0",
    )

    steps = (
        _step(1, "s-01", StepType.CHECK),
        _step(2, "s-02", StepType.VALIDATION),
    )

    with pytest.raises(ValueError):
        validator.validate(runbook, steps)


def test_definition_validation_with_steps(runbook_definition):

    validator = RunbookValidator()

    assert validator.validate(runbook_definition) is True


def test_definition_by_order(runbook_definition):

    assert [s.order for s in runbook_definition.by_order()] == [1, 2, 3, 4, 5, 6]


def test_definition_action_for_step(runbook_definition):

    assert runbook_definition.action_for_step(
        runbook_definition.step("svc-03")
    ) is None

    assert runbook_definition.step("svc-99") is None


def test_action_linked_to_step():

    from services.operations import RunbookAction

    definition = RunbookDefinition(
        runbook_id="RB-001",
        name="Test",
        description="Test",
        severity=RunbookSeverity.STANDARD,
        version="1.0.0",
        steps=_valid_steps(),
        actions=(
            RunbookAction(
                action_id="s-02",
                name="Do",
                control_action="PAUSE_TRADING",
            ),
        ),
    )

    action = definition.action_for_step(definition.step("s-02"))

    assert action is not None
    assert action.control_action == "PAUSE_TRADING"
