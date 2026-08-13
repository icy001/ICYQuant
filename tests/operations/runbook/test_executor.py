"""Runbook executor tests (Commit 27 Part 1.5, spec sections 28, 31-32)."""

import pytest

from services.operations import (
    RunbookDefinition,
    RunbookExecutor,
    RunbookSeverity,
    RunbookStep,
    StepStatus,
    StepType,
)


def _step(order, step_id, step_type, required=True):
    return RunbookStep(
        step_id=step_id,
        order=order,
        name=step_id,
        step_type=step_type,
        description=step_id,
        required=required,
    )


def _definition():
    return RunbookDefinition(
        runbook_id="RB-TEST-001",
        name="Test",
        description="Test",
        severity=RunbookSeverity.STANDARD,
        version="1.0.0",
        steps=(
            _step(1, "s-01", StepType.CHECK),
            _step(2, "s-02", StepType.VALIDATION),
        ),
    )


def test_execute_step_marks_completed():

    executor = RunbookExecutor()

    execution = executor.begin(
        incident_id="INC-001",
        runbook=_definition(),
    )

    step = _definition().step("s-01")

    assert executor.execute_step(
        execution,
        step,
        operator="ops-01",
        result="PASSED",
    )

    assert executor.completed(execution, "s-01")
    assert execution.status("s-01") is StepStatus.PASSED


def test_execute_step_creates_audit_record():
    # spec section 31: 每一步必须记录 operator / result / timestamp
    executor = RunbookExecutor()

    execution = executor.begin(
        incident_id="INC-001",
        runbook=_definition(),
    )

    step = _definition().step("s-01")

    executor.execute_step(
        execution,
        step,
        operator="ops-01",
        result="PASSED",
    )

    assert execution.incident_id == "INC-001"
    assert execution.runbook_id == "RB-TEST-001"
    assert execution.runbook_version == "1.0.0"

    events = execution.events()

    assert len(events) == 1
    assert events[0].step_id == "s-01"
    assert events[0].operator == "ops-01"
    assert events[0].result == "PASSED"


def test_skip_requires_reason():
    # spec section 32: 跳步必须有 reason / actor / timestamp
    executor = RunbookExecutor()

    execution = executor.begin(
        incident_id="INC-001",
        runbook=_definition(),
    )

    step = _definition().step("s-02")

    with pytest.raises(ValueError):
        executor.skip_step(
            execution,
            step,
            operator="ops-01",
            reason="",
        )


def test_skip_records_skipped():

    executor = RunbookExecutor()

    execution = executor.begin(
        incident_id="INC-001",
        runbook=_definition(),
    )

    step = _definition().step("s-02")

    assert executor.skip_step(
        execution,
        step,
        operator="ops-01",
        reason="manually skipped by operator",
    )

    record = execution.records["s-02"]

    assert record.status is StepStatus.SKIPPED
    assert record.operator == "ops-01"
    assert "manually skipped" in record.reason


def test_optional_step_is_skipped_with_record():

    executor = RunbookExecutor()

    definition = RunbookDefinition(
        runbook_id="RB-TEST-002",
        name="Test",
        description="Test",
        severity=RunbookSeverity.STANDARD,
        version="1.0.0",
        steps=(
            _step(1, "s-01", StepType.CHECK),
            _step(2, "s-02", StepType.VALIDATION, required=False),
        ),
    )

    execution = executor.begin("INC-001", definition)

    executor.execute_step(
        execution,
        definition.step("s-02"),
        operator="ops-01",
    )

    assert execution.status("s-02") is StepStatus.SKIPPED


def test_fail_step():

    executor = RunbookExecutor()

    execution = executor.begin(
        incident_id="INC-001",
        runbook=_definition(),
    )

    step = _definition().step("s-01")

    executor.fail_step(
        execution,
        step,
        operator="ops-01",
        reason="check failed",
    )

    assert execution.status("s-01") is StepStatus.FAILED
    assert len(execution.failed_steps) == 1


def test_duplicate_execute_is_idempotent():

    executor = RunbookExecutor()

    execution = executor.begin(
        incident_id="INC-001",
        runbook=_definition(),
    )

    step = _definition().step("s-01")

    assert executor.execute_step(execution, step)
    assert not executor.execute_step(execution, step)
    assert len(execution.records) == 1


def test_required_steps_passed():

    executor = RunbookExecutor()

    definition = _definition()

    execution = executor.begin("INC-001", definition)

    for step in definition.steps:
        executor.execute_step(execution, step)

    assert executor.required_steps_passed(execution, definition)


def test_required_steps_not_all_passed():

    executor = RunbookExecutor()

    definition = _definition()

    execution = executor.begin("INC-001", definition)

    executor.execute_step(
        execution,
        definition.step("s-01"),
    )

    assert not executor.required_steps_passed(execution, definition)
