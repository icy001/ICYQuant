"""Tests for services.governance.condition (Commit 28 Part 1.2)."""

import pytest

from services.governance.condition import (
    ConditionEvaluator,
    ConditionOperator,
    PolicyCondition,
)
from services.governance.decision import GovernanceContext


def _context(**overrides):
    base = dict(
        principal_id="ops-001",
        role_ids=("OPERATOR",),
        resource="trading",
        action="pause",
        environment="production",
    )
    base.update(overrides)
    return GovernanceContext(**base)


def test_condition_construction():
    condition = PolicyCondition(
        field="severity",
        operator=ConditionOperator.IN,
        value=("CRITICAL", "EMERGENCY"),
    )
    assert condition.field == "severity"
    assert condition.operator == ConditionOperator.IN
    assert condition.value == ("CRITICAL", "EMERGENCY")


def test_condition_is_frozen():
    condition = PolicyCondition("severity", ConditionOperator.EQUALS, "CRITICAL")
    with pytest.raises(Exception):
        condition.value = "WARNING"  # type: ignore[misc]


def test_equals():
    evaluator = ConditionEvaluator()
    condition = PolicyCondition("environment", ConditionOperator.EQUALS, "production")
    assert evaluator.evaluate(condition, _context())
    assert not evaluator.evaluate(condition, _context(environment="staging"))


def test_not_equals():
    evaluator = ConditionEvaluator()
    condition = PolicyCondition("environment", ConditionOperator.NOT_EQUALS, "production")
    assert evaluator.evaluate(condition, _context(environment="staging"))
    assert not evaluator.evaluate(condition, _context())


def test_in():
    evaluator = ConditionEvaluator()
    condition = PolicyCondition(
        field="severity",
        operator=ConditionOperator.IN,
        value=("CRITICAL", "EMERGENCY"),
    )
    assert evaluator.evaluate(condition, _context(severity="CRITICAL"))
    assert evaluator.evaluate(condition, _context(severity="EMERGENCY"))
    assert not evaluator.evaluate(condition, _context(severity="WARNING"))


def test_not_in():
    evaluator = ConditionEvaluator()
    condition = PolicyCondition(
        field="severity",
        operator=ConditionOperator.NOT_IN,
        value=("CRITICAL", "EMERGENCY"),
    )
    assert evaluator.evaluate(condition, _context(severity="WARNING"))
    assert not evaluator.evaluate(condition, _context(severity="CRITICAL"))


def test_exists():
    evaluator = ConditionEvaluator()
    condition = PolicyCondition("approval_id", ConditionOperator.EXISTS, None)
    assert evaluator.evaluate(condition, _context(approval_id="APR-001"))
    assert not evaluator.evaluate(condition, _context())


def test_missing_field_behaves_as_none():
    evaluator = ConditionEvaluator()
    exists = PolicyCondition("approval_id", ConditionOperator.EXISTS, None)
    equals_none = PolicyCondition("approval_id", ConditionOperator.EQUALS, None)
    assert not evaluator.evaluate(exists, _context())
    assert evaluator.evaluate(equals_none, _context())


def test_unknown_operator_returns_false():
    evaluator = ConditionEvaluator()
    condition = PolicyCondition(
        field="severity",
        operator=ConditionOperator.EQUALS,
        value="CRITICAL",
    )
    assert not evaluator.evaluate(condition, object())
