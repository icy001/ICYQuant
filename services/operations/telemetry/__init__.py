"""Metrics & Telemetry Layer (Commit 27 Part 1.2).

Telemetry 描述"系统刚刚发生了什么"：

    Service -> Telemetry (Metrics / Health / Events / Runtime Context)
        -> Operations -> Alerting -> Incident

核心原则（spec section 23）：

    Metrics    描述"系统现在怎么样"
    Telemetry  描述"系统刚刚发生了什么"

Telemetry 只负责记录，不参与交易决策：

    错误：if latency > 500: reject_order()
    正确：Telemetry -> Metric -> Alert -> Incident -> Control Plane
"""

from ..models.telemetry import TelemetryContext
from .counter import Counter
from .gauge import Gauge
from .histogram import Histogram
from .metric import MetricDefinition, MetricType
from .recorder import MetricSample, TelemetryRecorder
from .registry import MetricRegistry
from .schema import (
    FORBIDDEN_LABELS,
    RECOMMENDED_LABELS,
    control_plane_metrics,
    ledger_metrics,
    position_metrics,
    reconciliation_metrics,
    recovery_metrics,
    register_standard_metrics,
    standard_metrics,
    system_gauges,
    trading_metrics,
    venue_metrics,
)

__all__ = [
    "Counter",
    "FORBIDDEN_LABELS",
    "Gauge",
    "Histogram",
    "MetricDefinition",
    "MetricRegistry",
    "MetricSample",
    "MetricType",
    "RECOMMENDED_LABELS",
    "TelemetryContext",
    "TelemetryRecorder",
    "control_plane_metrics",
    "ledger_metrics",
    "position_metrics",
    "reconciliation_metrics",
    "recovery_metrics",
    "register_standard_metrics",
    "standard_metrics",
    "system_gauges",
    "trading_metrics",
    "venue_metrics",
]
