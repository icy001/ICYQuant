"""Runbook step tests (Commit 27 Part 1.5, spec sections 5-6)."""

import pytest

from services.operations import RunbookStep, StepType


def test_step_type_values():

    assert StepType.CHECK.value == "CHECK"
    assert StepType.ACTION.value == "ACTION"
    assert StepType.APPROVAL.value == "APPROVAL"
    assert StepType.WAIT.value == "WAIT"
    assert StepType.VALIDATION.value == "VALIDATION"


def test_step_defaults():

    step = RunbookStep(
        step_id="s-01",
        order=1,
        name="Health",
        step_type=StepType.CHECK,
        description="Service health",
    )

    assert step.required is True
    assert step.timeout_seconds == 60


def test_step_is_frozen():

    step = RunbookStep(
        step_id="s-01",
        order=1,
        name="Health",
        step_type=StepType.CHECK,
        description="Service health",
    )

    with pytest.raises(Exception):
        step.timeout_seconds = 30


def test_typical_pipeline():

    pipeline = (
        StepType.CHECK,
        StepType.CHECK,
        StepType.ACTION,
        StepType.APPROVAL,
        StepType.ACTION,
        StepType.WAIT,
        StepType.VALIDATION,
    )

    assert len(pipeline) == 7
