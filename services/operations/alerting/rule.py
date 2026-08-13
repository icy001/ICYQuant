"""Alert rule (Commit 27 Part 1.3, spec sections 7, 9-11, 28).

例如：

    rule_id:    execution-latency-high
    metric:     execution_latency_ms
    operator:   >
    threshold:  100
    severity:   WARNING

duration_seconds（spec section 24）：条件需要持续 N 秒才触发，避免单次抖动。

Hysteresis（spec section 25）：恢复阈值不能总是和触发阈值一样，否则
100/99/101/99 会造成 Alert Flapping。后续版本 Rule Model 将预留
trigger_threshold / resolve_threshold。
"""

from __future__ import annotations

from dataclasses import dataclass

from .severity import AlertSeverity


@dataclass(frozen=True)
class AlertRule:

    rule_id: str

    name: str

    metric_name: str

    severity: AlertSeverity

    threshold: float

    operator: str

    duration_seconds: int = 0

    enabled: bool = True

    service_id: str | None = None


def standard_rules() -> tuple[AlertRule, ...]:
    """第一批标准生产 Alert Rules（spec section 28）。

    覆盖：Service Health / Event Bus / Orders / Risk / Execution /
    Venue / Reconciliation / Global Kill / Recovery。
    """

    return (
        AlertRule(
            rule_id="service-unhealthy",
            name="Service unhealthy",
            metric_name="service_unhealthy",
            severity=AlertSeverity.CRITICAL,
            threshold=0,
            operator=">",
        ),
        AlertRule(
            rule_id="service-degraded",
            name="Service degraded",
            metric_name="service_degraded",
            severity=AlertSeverity.WARNING,
            threshold=0,
            operator=">",
        ),
        AlertRule(
            rule_id="event-bus-failure",
            name="Event bus failure",
            metric_name="events_failed_total",
            severity=AlertSeverity.ERROR,
            threshold=0,
            operator=">",
        ),
        AlertRule(
            rule_id="order-reject-rate-high",
            name="Order rejection rate high",
            metric_name="order_reject_rate",
            severity=AlertSeverity.CRITICAL,
            threshold=0.10,
            operator=">",
        ),
        AlertRule(
            rule_id="order-failure-rate-high",
            name="Order failure rate high",
            metric_name="order_failure_rate",
            severity=AlertSeverity.ERROR,
            threshold=0.05,
            operator=">",
        ),
        AlertRule(
            rule_id="risk-check-latency-high",
            name="Risk check latency high",
            metric_name="risk_check_latency_ms",
            severity=AlertSeverity.ERROR,
            threshold=50,
            operator=">",
        ),
        AlertRule(
            rule_id="risk-rejection-spike",
            name="Risk rejection spike",
            metric_name="risk_rejected_total",
            severity=AlertSeverity.CRITICAL,
            threshold=100,
            operator=">",
        ),
        AlertRule(
            rule_id="execution-latency-high",
            name="Execution latency high",
            metric_name="execution_latency_ms",
            severity=AlertSeverity.WARNING,
            threshold=100,
            operator=">",
            duration_seconds=30,
        ),
        AlertRule(
            rule_id="execution-failure-spike",
            name="Execution failure spike",
            metric_name="execution_failure_total",
            severity=AlertSeverity.ERROR,
            threshold=50,
            operator=">",
        ),
        AlertRule(
            rule_id="venue-disconnected",
            name="Venue disconnected",
            metric_name="venue_heartbeat_failures_total",
            severity=AlertSeverity.ERROR,
            threshold=0,
            operator=">",
        ),
        AlertRule(
            rule_id="venue-latency-high",
            name="Venue latency high",
            metric_name="venue_latency_ms",
            severity=AlertSeverity.WARNING,
            threshold=150,
            operator=">",
        ),
        AlertRule(
            rule_id="venue-rejection-spike",
            name="Venue rejection spike",
            metric_name="venue_orders_rejected_total",
            severity=AlertSeverity.ERROR,
            threshold=50,
            operator=">",
        ),
        AlertRule(
            rule_id="reconciliation-difference",
            name="Position reconciliation difference",
            metric_name="reconciliation_differences_total",
            severity=AlertSeverity.CRITICAL,
            threshold=0,
            operator=">",
        ),
        AlertRule(
            rule_id="global-kill-activated",
            name="Global kill switch activated",
            metric_name="control_kills_total",
            severity=AlertSeverity.EMERGENCY,
            threshold=0,
            operator=">",
        ),
        AlertRule(
            rule_id="recovery-failed",
            name="Recovery failed",
            metric_name="control_recovery_failed_total",
            severity=AlertSeverity.CRITICAL,
            threshold=0,
            operator=">",
        ),
    )
