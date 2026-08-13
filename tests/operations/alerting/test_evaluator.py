"""
Tests for AlertRuleEvaluator (Commit 27 Part 1.3, spec sections 12, 31).

先检查 rule.enabled，再评估条件。
"""

from __future__ import annotations

from services.operations import (
    AlertRule,
    AlertRuleEvaluator,
    AlertSeverity,
    ConditionEvaluator,
)


def _rule(**overrides) -> AlertRule:
    fields = dict(
        rule_id="execution-latency-high",
        name="Execution latency high",
        metric_name="execution_latency_ms",
        severity=AlertSeverity.WARNING,
        threshold=100,
        operator=">",
    )
    fields.update(overrides)
    return AlertRule(**fields)


def _evaluator() -> AlertRuleEvaluator:
    return AlertRuleEvaluator(ConditionEvaluator())


def test_disabled_rule_does_not_fire():
    """spec section 31: enabled=False 时不触发。"""
    rule = _rule(enabled=False)

    evaluator = _evaluator()

    assert not evaluator.evaluate(rule, 200)


def test_enabled_rule_fires_above_threshold():
    rule = _rule()

    evaluator = _evaluator()

    assert evaluator.evaluate(rule, 200)


def test_enabled_rule_does_not_fire_below_threshold():
    rule = _rule()

    evaluator = _evaluator()

    assert not evaluator.evaluate(rule, 50)


def test_evaluator_uses_rule_operator():
    rule = _rule(operator="<", threshold=100)

    evaluator = _evaluator()

    assert evaluator.evaluate(rule, 50)

    assert not evaluator.evaluate(rule, 150)
