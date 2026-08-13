"""Standard ICYQuant metrics schema (Commit 27 Part 1.2, spec sections 15-22).

本模块把 Trading / Venue / Control / Recovery 指标作为稳定系统契约，
防止不同服务随意定义：

    orders_total / order_count / total_orders / submitted_orders

命名约定（spec section 21）：<domain>_<action>_<unit>

    orders_submitted_total        counter
    open_orders                   gauge
    risk_check_latency_ms         histogram

单位必须明确（spec section 22）：

    latency_ms / duration_ms / notional_usd / quantity / ratio

Label 治理（spec section 20）：

    推荐：service / instance / environment / venue / strategy /
          portfolio / status / order_type

    禁止：order_id / trade_id / trace_id / request_id / incident_id
    （高基数标识符进入 Logs / Traces / Events，而不是 Metrics）
"""

from __future__ import annotations

from .counter import Counter
from .gauge import Gauge
from .histogram import Histogram
from .metric import MetricDefinition, MetricType
from .registry import MetricRegistry

RECOMMENDED_LABELS = frozenset({
    "service",
    "instance",
    "environment",
    "venue",
    "strategy",
    "portfolio",
    "status",
    "order_type",
})

FORBIDDEN_LABELS = frozenset({
    "order_id",
    "trade_id",
    "trace_id",
    "request_id",
    "incident_id",
})


def trading_metrics() -> tuple[MetricDefinition, ...]:
    """Orders / Execution / Risk / Event Bus（spec section 15）。"""

    return (
        # Orders
        MetricDefinition(
            name="orders_submitted_total",
            metric_type=MetricType.COUNTER,
            description="Total submitted orders",
            unit="orders",
        ),
        MetricDefinition(
            name="orders_accepted_total",
            metric_type=MetricType.COUNTER,
            description="Total accepted orders",
            unit="orders",
        ),
        MetricDefinition(
            name="orders_rejected_total",
            metric_type=MetricType.COUNTER,
            description="Total rejected orders",
            unit="orders",
        ),
        MetricDefinition(
            name="orders_cancelled_total",
            metric_type=MetricType.COUNTER,
            description="Total cancelled orders",
            unit="orders",
        ),
        MetricDefinition(
            name="orders_filled_total",
            metric_type=MetricType.COUNTER,
            description="Total filled orders",
            unit="orders",
        ),
        MetricDefinition(
            name="orders_failed_total",
            metric_type=MetricType.COUNTER,
            description="Total failed orders",
            unit="orders",
        ),
        # Execution
        MetricDefinition(
            name="execution_requests_total",
            metric_type=MetricType.COUNTER,
            description="Total execution requests",
            unit="requests",
        ),
        MetricDefinition(
            name="execution_success_total",
            metric_type=MetricType.COUNTER,
            description="Total successful executions",
            unit="executions",
        ),
        MetricDefinition(
            name="execution_failure_total",
            metric_type=MetricType.COUNTER,
            description="Total failed executions",
            unit="executions",
        ),
        MetricDefinition(
            name="execution_latency_ms",
            metric_type=MetricType.HISTOGRAM,
            description="Execution latency",
            unit="ms",
        ),
        # Risk
        MetricDefinition(
            name="risk_checks_total",
            metric_type=MetricType.COUNTER,
            description="Total risk checks performed",
            unit="checks",
        ),
        MetricDefinition(
            name="risk_approved_total",
            metric_type=MetricType.COUNTER,
            description="Total risk checks approved",
            unit="checks",
        ),
        MetricDefinition(
            name="risk_rejected_total",
            metric_type=MetricType.COUNTER,
            description="Total risk checks rejected",
            unit="checks",
        ),
        MetricDefinition(
            name="risk_check_latency_ms",
            metric_type=MetricType.HISTOGRAM,
            description="Risk check latency",
            unit="ms",
        ),
        # Event Bus
        MetricDefinition(
            name="events_published_total",
            metric_type=MetricType.COUNTER,
            description="Total events published",
            unit="events",
        ),
        MetricDefinition(
            name="events_consumed_total",
            metric_type=MetricType.COUNTER,
            description="Total events consumed",
            unit="events",
        ),
        MetricDefinition(
            name="events_failed_total",
            metric_type=MetricType.COUNTER,
            description="Total events failed",
            unit="events",
        ),
        MetricDefinition(
            name="event_processing_latency_ms",
            metric_type=MetricType.HISTOGRAM,
            description="Event processing latency",
            unit="ms",
        ),
    )


def ledger_metrics() -> tuple[MetricDefinition, ...]:
    """Ledger metrics（spec section 16）。"""

    return (
        MetricDefinition(
            name="ledger_events_total",
            metric_type=MetricType.COUNTER,
            description="Total ledger events written",
            unit="events",
        ),
        MetricDefinition(
            name="ledger_write_failures_total",
            metric_type=MetricType.COUNTER,
            description="Total ledger write failures",
            unit="events",
        ),
        MetricDefinition(
            name="ledger_write_latency_ms",
            metric_type=MetricType.HISTOGRAM,
            description="Ledger write latency",
            unit="ms",
        ),
    )


def position_metrics() -> tuple[MetricDefinition, ...]:
    """Position metrics（spec section 16）。"""

    return (
        MetricDefinition(
            name="position_updates_total",
            metric_type=MetricType.COUNTER,
            description="Total position updates",
            unit="updates",
        ),
        MetricDefinition(
            name="position_rebuilds_total",
            metric_type=MetricType.COUNTER,
            description="Total position rebuilds",
            unit="rebuilds",
        ),
        MetricDefinition(
            name="position_update_failures_total",
            metric_type=MetricType.COUNTER,
            description="Total position update failures",
            unit="updates",
        ),
    )


def reconciliation_metrics() -> tuple[MetricDefinition, ...]:
    """Reconciliation metrics（spec section 16）。"""

    return (
        MetricDefinition(
            name="reconciliation_runs_total",
            metric_type=MetricType.COUNTER,
            description="Total reconciliation runs",
            unit="runs",
        ),
        MetricDefinition(
            name="reconciliation_failures_total",
            metric_type=MetricType.COUNTER,
            description="Total reconciliation failures",
            unit="runs",
        ),
        MetricDefinition(
            name="reconciliation_differences_total",
            metric_type=MetricType.COUNTER,
            description="Total reconciliation differences found",
            unit="differences",
        ),
        MetricDefinition(
            name="reconciliation_repairs_total",
            metric_type=MetricType.COUNTER,
            description="Total reconciliation repairs applied",
            unit="repairs",
        ),
        MetricDefinition(
            name="reconciliation_latency_ms",
            metric_type=MetricType.HISTOGRAM,
            description="Reconciliation latency",
            unit="ms",
        ),
    )


def venue_metrics() -> tuple[MetricDefinition, ...]:
    """Venue metrics，统一带 venue Label（spec section 17）。"""

    return (
        MetricDefinition(
            name="venue_orders_submitted_total",
            metric_type=MetricType.COUNTER,
            description="Total orders submitted per venue",
            unit="orders",
            labels=("venue",),
        ),
        MetricDefinition(
            name="venue_orders_accepted_total",
            metric_type=MetricType.COUNTER,
            description="Total orders accepted per venue",
            unit="orders",
            labels=("venue",),
        ),
        MetricDefinition(
            name="venue_orders_rejected_total",
            metric_type=MetricType.COUNTER,
            description="Total orders rejected per venue",
            unit="orders",
            labels=("venue",),
        ),
        MetricDefinition(
            name="venue_cancel_success_total",
            metric_type=MetricType.COUNTER,
            description="Total successful cancels per venue",
            unit="cancels",
            labels=("venue",),
        ),
        MetricDefinition(
            name="venue_cancel_failure_total",
            metric_type=MetricType.COUNTER,
            description="Total failed cancels per venue",
            unit="cancels",
            labels=("venue",),
        ),
        MetricDefinition(
            name="venue_latency_ms",
            metric_type=MetricType.HISTOGRAM,
            description="Venue latency",
            unit="ms",
            labels=("venue",),
        ),
        MetricDefinition(
            name="venue_heartbeat_failures_total",
            metric_type=MetricType.COUNTER,
            description="Total venue heartbeat failures",
            unit="failures",
            labels=("venue",),
        ),
    )


def control_plane_metrics() -> tuple[MetricDefinition, ...]:
    """Control Plane metrics（spec section 18）。

    运营人员可以直接回答：今天发生了几次 Kill？过去 1 小时几次 Venue Failover？
    """

    return (
        MetricDefinition(
            name="control_blocks_total",
            metric_type=MetricType.COUNTER,
            description="Total control actions blocking new risk",
            unit="actions",
        ),
        MetricDefinition(
            name="control_kills_total",
            metric_type=MetricType.COUNTER,
            description="Total global kill switch activations",
            unit="actions",
        ),
        MetricDefinition(
            name="control_pauses_total",
            metric_type=MetricType.COUNTER,
            description="Total control pauses",
            unit="actions",
        ),
        MetricDefinition(
            name="control_failovers_total",
            metric_type=MetricType.COUNTER,
            description="Total venue failovers",
            unit="actions",
        ),
        MetricDefinition(
            name="control_recovery_started_total",
            metric_type=MetricType.COUNTER,
            description="Total recovery processes started",
            unit="actions",
        ),
        MetricDefinition(
            name="control_recovery_completed_total",
            metric_type=MetricType.COUNTER,
            description="Total recovery processes completed",
            unit="actions",
        ),
        MetricDefinition(
            name="control_recovery_failed_total",
            metric_type=MetricType.COUNTER,
            description="Total recovery processes failed",
            unit="actions",
        ),
    )


def recovery_metrics() -> tuple[MetricDefinition, ...]:
    """Recovery metrics（spec section 19）。

    直接回答：为什么系统还没有恢复交易？
    例如 "Recovery blocked: Position reconciliation incomplete"。
    """

    return (
        MetricDefinition(
            name="recovery_validation_total",
            metric_type=MetricType.COUNTER,
            description="Total recovery validations performed",
            unit="validations",
        ),
        MetricDefinition(
            name="recovery_validation_failed_total",
            metric_type=MetricType.COUNTER,
            description="Total recovery validations failed",
            unit="validations",
        ),
        MetricDefinition(
            name="recovery_approval_total",
            metric_type=MetricType.COUNTER,
            description="Total recovery manual approvals",
            unit="approvals",
        ),
        MetricDefinition(
            name="recovery_resume_total",
            metric_type=MetricType.COUNTER,
            description="Total recovery resumes",
            unit="resumes",
        ),
        MetricDefinition(
            name="recovery_blocked_reconciliation_total",
            metric_type=MetricType.COUNTER,
            description="Total recovery blocks due to reconciliation",
            unit="blocks",
        ),
        MetricDefinition(
            name="recovery_blocked_risk_total",
            metric_type=MetricType.COUNTER,
            description="Total recovery blocks due to risk state",
            unit="blocks",
        ),
        MetricDefinition(
            name="recovery_blocked_execution_total",
            metric_type=MetricType.COUNTER,
            description="Total recovery blocks due to execution",
            unit="blocks",
        ),
        MetricDefinition(
            name="recovery_blocked_venue_total",
            metric_type=MetricType.COUNTER,
            description="Total recovery blocks due to venue",
            unit="blocks",
        ),
    )


def system_gauges() -> tuple[MetricDefinition, ...]:
    """当前状态类 Gauge（spec sections 3, 8）。"""

    return (
        MetricDefinition(
            name="open_orders",
            metric_type=MetricType.GAUGE,
            description="Current open orders",
            unit="orders",
        ),
        MetricDefinition(
            name="active_positions",
            metric_type=MetricType.GAUGE,
            description="Current active positions",
            unit="positions",
        ),
        MetricDefinition(
            name="connected_venues",
            metric_type=MetricType.GAUGE,
            description="Currently connected venues",
            unit="venues",
        ),
        MetricDefinition(
            name="queue_depth",
            metric_type=MetricType.GAUGE,
            description="Current event queue depth",
            unit="events",
        ),
        MetricDefinition(
            name="risk_utilization",
            metric_type=MetricType.GAUGE,
            description="Current risk budget utilization",
            unit="ratio",
        ),
    )


def standard_metrics() -> tuple[MetricDefinition, ...]:
    """全部标准指标（稳定系统契约）。"""

    return (
        trading_metrics()
        + ledger_metrics()
        + position_metrics()
        + reconciliation_metrics()
        + venue_metrics()
        + control_plane_metrics()
        + recovery_metrics()
        + system_gauges()
    )


def register_standard_metrics(
    registry: MetricRegistry,
) -> None:
    """把标准指标实例化并注册到 Registry。

    后续 Alerting / Snapshot 直接使用 standard_metrics 契约。
    """

    for definition in standard_metrics():

        if definition.metric_type == MetricType.COUNTER:
            metric = Counter(definition)

        elif definition.metric_type == MetricType.GAUGE:
            metric = Gauge(definition)

        else:
            metric = Histogram(definition)

        registry.register(metric)
