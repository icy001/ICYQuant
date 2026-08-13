"""
Tests for AlertRule and standard rules (Commit 27 Part 1.3, spec sections 7, 9-11, 28).
"""

from __future__ import annotations

from services.operations import (
    AlertRule,
    AlertSeverity,
    standard_rules,
)


def test_rule_defaults():
    """spec section 7: duration/enabled/service_id 有默认值。"""
    rule = AlertRule(
        rule_id="execution-latency-high",
        name="Execution latency high",
        metric_name="execution_latency_ms",
        severity=AlertSeverity.WARNING,
        threshold=100,
        operator=">",
    )

    assert rule.duration_seconds == 0
    assert rule.enabled is True
    assert rule.service_id is None


def test_rule_duration_seconds_configurable():
    """spec section 24: 条件需持续 N 秒才触发。"""
    rule = AlertRule(
        rule_id="execution-latency-high",
        name="Execution latency high",
        metric_name="execution_latency_ms",
        severity=AlertSeverity.WARNING,
        threshold=100,
        operator=">",
        duration_seconds=30,
    )

    assert rule.duration_seconds == 30


def test_rule_is_frozen():
    rule = AlertRule(
        rule_id="test",
        name="test",
        metric_name="latency",
        severity=AlertSeverity.WARNING,
        threshold=100,
        operator=">",
    )

    import dataclasses

    try:
        rule.threshold = 200
    except dataclasses.FrozenInstanceError:
        pass
    else:
        raise AssertionError("AlertRule should be frozen")


def test_reconciliation_difference_is_critical():
    """spec section 10: Position != Ledger 产生 CRITICAL。"""
    rules = {r.rule_id: r for r in standard_rules()}

    rule = rules["reconciliation-difference"]

    assert rule.metric_name == "reconciliation_differences_total"
    assert rule.severity == AlertSeverity.CRITICAL
    assert rule.operator == ">"
    assert rule.threshold == 0


def test_global_kill_activated_is_emergency():
    """spec section 11: Kill Switch 激活为 EMERGENCY。"""
    rules = {r.rule_id: r for r in standard_rules()}

    rule = rules["global-kill-activated"]

    assert rule.metric_name == "control_kills_total"
    assert rule.severity == AlertSeverity.EMERGENCY


def test_standard_rules_cover_spec_list():
    """spec section 28: 第一批标准规则全部存在。"""
    rule_ids = {r.rule_id for r in standard_rules()}

    assert {
        "service-unhealthy",
        "service-degraded",
        "event-bus-failure",
        "order-reject-rate-high",
        "order-failure-rate-high",
        "risk-check-latency-high",
        "risk-rejection-spike",
        "execution-latency-high",
        "execution-failure-spike",
        "venue-disconnected",
        "venue-latency-high",
        "venue-rejection-spike",
        "reconciliation-difference",
        "global-kill-activated",
        "recovery-failed",
    }.issubset(rule_ids)


def test_standard_rules_have_unique_ids():
    rules = standard_rules()

    ids = [r.rule_id for r in rules]

    assert len(ids) == len(set(ids))
