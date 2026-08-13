"""
Production Operations Layer (Commit 27 Part 1.1, 1.2).

Operations = 看清楚系统发生了什么
Control    = 决定系统允许做什么
Recovery   = 决定系统什么时候可以重新做

重要边界（spec sections 16-18）：

1. Operational Health 不是 Trading Health：
   Service = HEALTHY 不代表 Trading = SAFE（Position != Ledger 时
   Trading State = NOT SAFE）。

2. Operations 只负责 Observe，不执行控制：
   正确路径是 Operations -> Health Signal -> Incident -> Control Plane
   -> Kill / Pause / Failover。Observability 代码绝不能偷偷拥有交易
   控制权限。

3. Telemetry 只负责记录，不参与交易决策（Part 1.2 spec section 23）：
   Metrics 描述"系统现在怎么样"，Telemetry 描述"系统刚刚发生了什么"。
   错误：if latency > 500: reject_order()

4. Alert 是"发现异常"，不是"执行交易控制"（Part 1.3 spec section 29）：
   Kill / Pause / Freeze / Failover / Recovery 仍由 Control Plane 执行。
"""

from .alerting import (
    Alert,
    AlertDeduplicator,
    AlertFingerprint,
    AlertManager,
    AlertRule,
    AlertRuleEvaluator,
    AlertRouter,
    AlertSeverity,
    AlertState,
    AlertStormProtector,
    ConditionEvaluator,
    FlappingDetector,
    standard_rules,
)
from .health import ServiceHealthMonitor
from .models import (
    OperationalSnapshot,
    ServiceDependency,
    ServiceHealth,
    ServiceIdentity,
    ServiceState,
    TelemetryContext,
)
from .registry import (
    RegisteredService,
    ServiceRegistry,
    validate_dependency,
)
from .snapshot import OperationalSnapshotBuilder
from .telemetry import (
    Counter,
    FORBIDDEN_LABELS,
    Gauge,
    Histogram,
    MetricDefinition,
    MetricRegistry,
    MetricSample,
    MetricType,
    RECOMMENDED_LABELS,
    TelemetryRecorder,
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
    "Alert",
    "AlertDeduplicator",
    "AlertFingerprint",
    "AlertManager",
    "AlertRule",
    "AlertRuleEvaluator",
    "AlertRouter",
    "AlertSeverity",
    "AlertState",
    "AlertStormProtector",
    "ConditionEvaluator",
    "Counter",
    "FlappingDetector",
    "FORBIDDEN_LABELS",
    "Gauge",
    "Histogram",
    "MetricDefinition",
    "MetricRegistry",
    "MetricSample",
    "MetricType",
    "OperationalSnapshot",
    "OperationalSnapshotBuilder",
    "RECOMMENDED_LABELS",
    "RegisteredService",
    "ServiceDependency",
    "ServiceHealth",
    "ServiceHealthMonitor",
    "ServiceIdentity",
    "ServiceRegistry",
    "ServiceState",
    "TelemetryContext",
    "TelemetryRecorder",
    "control_plane_metrics",
    "ledger_metrics",
    "position_metrics",
    "reconciliation_metrics",
    "recovery_metrics",
    "register_standard_metrics",
    "standard_metrics",
    "standard_rules",
    "system_gauges",
    "trading_metrics",
    "validate_dependency",
    "venue_metrics",
]
