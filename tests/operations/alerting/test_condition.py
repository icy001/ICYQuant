"""
Tests for ConditionEvaluator (Commit 27 Part 1.3, spec sections 8, 30).

支持 6 种比较运算符；未知运算符抛 ValueError。
"""

from __future__ import annotations

import pytest

from services.operations import ConditionEvaluator


def test_condition_greater_than():
    """spec section 30: 120 > 100 为 True，80 > 100 为 False。"""
    evaluator = ConditionEvaluator()

    assert evaluator.evaluate(120, ">", 100)

    assert not evaluator.evaluate(80, ">", 100)


def test_condition_greater_or_equal():
    evaluator = ConditionEvaluator()

    assert evaluator.evaluate(100, ">=", 100)

    assert not evaluator.evaluate(99, ">=", 100)


def test_condition_less_than():
    evaluator = ConditionEvaluator()

    assert evaluator.evaluate(80, "<", 100)

    assert not evaluator.evaluate(120, "<", 100)


def test_condition_less_or_equal():
    evaluator = ConditionEvaluator()

    assert evaluator.evaluate(100, "<=", 100)

    assert not evaluator.evaluate(101, "<=", 100)


def test_condition_equal():
    evaluator = ConditionEvaluator()

    assert evaluator.evaluate(42, "==", 42)

    assert not evaluator.evaluate(43, "==", 42)


def test_condition_not_equal():
    evaluator = ConditionEvaluator()

    assert evaluator.evaluate(43, "!=", 42)

    assert not evaluator.evaluate(42, "!=", 42)


def test_condition_rejects_unknown_operator():
    evaluator = ConditionEvaluator()

    with pytest.raises(ValueError):
        evaluator.evaluate(120, "=>", 100)
