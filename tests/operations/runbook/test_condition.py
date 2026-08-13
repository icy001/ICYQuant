"""Runbook condition tests (Commit 27 Part 1.5)."""

import pytest

from services.operations import (
    ConditionOperator,
    RunbookCondition,
    evaluate_condition,
)


def test_gt_threshold():

    condition = RunbookCondition(
        condition_id="latency",
        description="Execution latency high",
        metric="execution_latency_ms",
        operator=ConditionOperator.GT,
        threshold=100,
    )

    assert evaluate_condition(condition, 150)
    assert not evaluate_condition(condition, 80)


def test_lte_threshold():

    condition = RunbookCondition(
        condition_id="backlog",
        description="Event backlog low",
        metric="event_backlog",
        operator=ConditionOperator.LTE,
        threshold=500,
    )

    assert evaluate_condition(condition, 120)
    assert not evaluate_condition(condition, 900)


def test_symbol_operators():

    condition = RunbookCondition(
        condition_id="rejects",
        description="Reject rate",
        metric="reject_rate",
        operator=">=",
        threshold=0.05,
    )

    assert evaluate_condition(condition, 0.08)
    assert not evaluate_condition(condition, 0.01)


def test_expected_string_match():

    condition = RunbookCondition(
        condition_id="venue",
        description="Venue connected",
        expected="CONNECTED",
    )

    assert evaluate_condition(condition, "CONNECTED")
    assert not evaluate_condition(condition, "DISCONNECTED")


def test_ne():

    condition = RunbookCondition(
        condition_id="state",
        description="Not degraded",
        operator=ConditionOperator.NE,
        threshold=0,
    )

    assert evaluate_condition(condition, 1)
    assert not evaluate_condition(condition, 0)


def test_missing_operator_raises():

    condition = RunbookCondition(
        condition_id="bad",
        description="Incomplete condition",
        metric="latency",
    )

    with pytest.raises(ValueError):
        evaluate_condition(condition, 150)


def test_unsupported_operator_raises():

    condition = RunbookCondition(
        condition_id="bad",
        description="Bad operator",
        metric="latency",
        operator="~~",
        threshold=10,
    )

    with pytest.raises(ValueError):
        evaluate_condition(condition, 150)
