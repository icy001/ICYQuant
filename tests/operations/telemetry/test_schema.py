"""
Tests for standard ICYQuant metrics schema (Commit 27 Part 1.2, spec sections 15-22).

验证命名约定、单位明确、Label 治理（推荐 / 禁止）。
"""

from __future__ import annotations

from services.operations import (
    FORBIDDEN_LABELS,
    RECOMMENDED_LABELS,
    MetricRegistry,
    MetricType,
    register_standard_metrics,
    standard_metrics,
)


def test_standard_metrics_cover_core_domains():
    """spec section 15-19: 覆盖 Orders/Risk/Execution/Venue/Control/Recovery。"""
    names = {m.name for m in standard_metrics()}

    assert {
        "orders_submitted_total",
        "orders_filled_total",
        "risk_checks_total",
        "execution_latency_ms",
        "events_failed_total",
        "ledger_write_failures_total",
        "position_rebuilds_total",
        "reconciliation_differences_total",
        "venue_orders_rejected_total",
        "control_kills_total",
        "recovery_approval_total",
    }.issubset(names)


def test_counter_names_follow_total_suffix():
    """spec section 21: Counter 统一 <domain>_<action>_total。"""
    for metric in standard_metrics():
        if metric.metric_type == MetricType.COUNTER:
            assert metric.name.endswith("_total"), metric.name


def test_histogram_names_include_unit():
    """spec section 22: 延迟类 Histogram 必须带 _ms 单位。"""
    for metric in standard_metrics():
        if metric.metric_type == MetricType.HISTOGRAM:
            assert metric.name.endswith("_ms"), metric.name
            assert metric.unit == "ms"


def test_venue_metrics_carry_venue_label():
    """spec section 17: Venue 指标带 venue Label。"""
    for metric in standard_metrics():
        if metric.name.startswith("venue_"):
            assert "venue" in metric.labels, metric.name


def test_metrics_never_use_forbidden_labels():
    """spec section 20: 高基数标识符禁止作为 Metrics Label。"""
    for metric in standard_metrics():
        for label in metric.labels:
            assert label not in FORBIDDEN_LABELS, (
                f"{metric.name} uses forbidden label {label}"
            )
            assert label in RECOMMENDED_LABELS, (
                f"{metric.name} uses non-standard label {label}"
            )


def test_register_standard_metrics_into_registry():
    registry = MetricRegistry()

    register_standard_metrics(registry)

    for metric in standard_metrics():
        assert registry.contains(metric.name)

    assert registry.contains("orders_submitted_total")
    assert registry.contains("control_kills_total")
    assert registry.contains("venue_orders_rejected_total")
