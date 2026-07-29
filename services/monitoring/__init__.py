"""ICYQuant Institutional Monitoring & Operations Center.

Unified monitoring platform covering:
- Service health & dependency checks
- Metrics collection, aggregation & time series
- Alert rule engine with multi-channel notification
- Auto-recovery, circuit breakers & failover
- 5 real-time dashboards (overview, trading, risk, portfolio, infrastructure)
- SLA tracking & reporting
"""

# Legacy exports (backward compatible)
from services.monitoring.metric import Metric
from services.monitoring.health import HealthStatus
from services.monitoring.monitor import ServiceHealth
from services.monitoring.collector import MetricsCollector as LegacyMetricsCollector
from services.monitoring.checker import HealthChecker
from services.monitoring.repository import MonitoringRepository
from services.monitoring.manager import MonitoringManager
from services.monitoring.service import MonitoringService

# Health sub-module
from services.monitoring.health.service_health import (
    ServiceHealthMonitor,
    ServiceStatus,
    HealthReport,
)
from services.monitoring.health.dependency_health import (
    DependencyChecker,
    DependencyStatus,
    DependencyReport,
)
from services.monitoring.health.readiness import (
    ReadinessProbe,
    ReadinessResult,
    ProbeType,
)

# Metrics sub-module
from services.monitoring.metrics.collector import (
    MetricsCollector,
    MetricType,
    BusinessMetrics,
    SystemMetrics,
)
from services.monitoring.metrics.aggregator import (
    MetricsAggregator,
    AggregationWindow,
    AggregatedStats,
)
from services.monitoring.metrics.timeseries import (
    TimeSeriesStore,
    DataPoint,
    TimeSeries,
)
from services.monitoring.metrics.exporter import (
    MetricsExporter,
    ExportFormat,
)

# Alert sub-module
from services.monitoring.alert.rule_engine import (
    AlertRuleEngine,
    AlertRule,
    AlertSeverity,
    AlertState,
    Alert,
)
from services.monitoring.alert.notifier import (
    AlertNotifier,
    NotificationChannel,
    Notification,
    ChannelConfig,
)
from services.monitoring.alert.escalation import (
    EscalationManager,
    EscalationPolicy,
    EscalationLevel,
)

# Recovery sub-module
from services.monitoring.recovery.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    CircuitBreakerRegistry,
    CircuitBreakerOpenError,
)
from services.monitoring.recovery.auto_recovery import (
    AutoRecovery,
    RecoveryAction,
    RecoveryResult,
    RecoveryStatus,
)
from services.monitoring.recovery.failover import (
    FailoverManager,
    FailoverTarget,
    FailoverStatus,
)

# Dashboard sub-module
from services.monitoring.dashboard.overview import (
    OverviewDashboard,
    SystemOverview,
)
from services.monitoring.dashboard.trading import (
    TradingDashboard,
    TradingSnapshot,
)
from services.monitoring.dashboard.risk import (
    RiskDashboard,
    RiskSnapshot,
)
from services.monitoring.dashboard.portfolio import (
    PortfolioDashboard,
    PortfolioSnapshot,
)
from services.monitoring.dashboard.infrastructure import (
    InfrastructureDashboard,
    InfrastructureSnapshot,
)

# Unified service
from services.monitoring.service import MonitoringCenter, SLAReport

# API router
from services.monitoring.api.monitoring_api import router as monitoring_router

__all__ = [
    # Legacy
    "Metric",
    "HealthStatus",
    "ServiceHealth",
    "LegacyMetricsCollector",
    "HealthChecker",
    "MonitoringRepository",
    "MonitoringManager",
    "MonitoringService",
    # Health
    "ServiceHealthMonitor",
    "ServiceStatus",
    "HealthReport",
    "DependencyChecker",
    "DependencyStatus",
    "DependencyReport",
    "ReadinessProbe",
    "ReadinessResult",
    "ProbeType",
    # Metrics
    "MetricsCollector",
    "MetricType",
    "BusinessMetrics",
    "SystemMetrics",
    "MetricsAggregator",
    "AggregationWindow",
    "AggregatedStats",
    "TimeSeriesStore",
    "DataPoint",
    "TimeSeries",
    "MetricsExporter",
    "ExportFormat",
    # Alerts
    "AlertRuleEngine",
    "AlertRule",
    "AlertSeverity",
    "AlertState",
    "Alert",
    "AlertNotifier",
    "NotificationChannel",
    "Notification",
    "ChannelConfig",
    "EscalationManager",
    "EscalationPolicy",
    "EscalationLevel",
    # Recovery
    "CircuitBreaker",
    "CircuitState",
    "CircuitBreakerRegistry",
    "CircuitBreakerOpenError",
    "AutoRecovery",
    "RecoveryAction",
    "RecoveryResult",
    "RecoveryStatus",
    "FailoverManager",
    "FailoverTarget",
    "FailoverStatus",
    # Dashboards
    "OverviewDashboard",
    "SystemOverview",
    "TradingDashboard",
    "TradingSnapshot",
    "RiskDashboard",
    "RiskSnapshot",
    "PortfolioDashboard",
    "PortfolioSnapshot",
    "InfrastructureDashboard",
    "InfrastructureSnapshot",
    # Unified
    "MonitoringCenter",
    "SLAReport",
    "monitoring_router",
]
