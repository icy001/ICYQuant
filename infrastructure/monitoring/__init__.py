"""
Monitoring infrastructure.

Provides the unified monitoring layer
for the ICYQuant platform, collecting
and aggregating metrics from all
infrastructure components (Database,
Redis, Kafka, Storage) and exporting
them to Prometheus/Grafana.

v0.4.0-alpha2 Part 5.5:
- MonitoringBootstrap for unified initialization
- MonitoringService for coordinated collection/export
- MonitoringScheduler for background collection
- MonitoringLifecycle for startup/shutdown management
- TelemetryService for unified metrics/traces/logs/events
- MonitoringTracing for pipeline performance tracing
- DIContainer for dependency injection
- Production monitoring platform V1 complete
"""

from .alert_models import (
    AlertEvent,
    AlertHistory,
    AlertLevel,
    AlertState,
)
from .alerts import (
    AlertEngine,
    AlertRouter,
    AlertRule,
    AlertRuleSet,
    AlertSuppression,
    BaseChannel,
    DingTalkChannel,
    EmailChannel,
    EnterpriseWeChatChannel,
    EscalationPolicy,
    LogChannel,
    NotificationChannel,
    PagerDutyChannel,
    RuleEvaluator,
    SlackChannel,
    WebhookChannel,
)
from .bootstrap import MonitoringBootstrap
from .collector import (
    BaseCollector,
    CollectorRunner,
    MetricsCollector,
)
from .collectors import (
    ApplicationCollector,
    BusinessCollector,
    DatabaseCollector,
    KafkaCollector,
    RedisCollector,
    StorageCollector,
)
from .config import MonitoringConfig
from .container import (
    DIContainer,
    register_monitoring,
)
from .dashboard_models import (
    DashboardCategory,
    DashboardPanel,
    DashboardTemplate,
    PanelType,
)
from .dashboards import (
    DASHBOARD_TEMPLATES,
    DashboardProvisioner,
    GrafanaDashboard,
    all_templates,
    get_template,
    list_templates,
)
from .exceptions import (
    CollectorError,
    ExporterError,
    HealthCheckError,
    MonitoringError,
    RegistryError,
)
from .exporter import (
    BaseExporter,
    MetricsExporter,
    PrometheusExporter,
)
from .health import MonitoringHealth
from .labels import (
    STANDARD_LABELS,
    build_default_labels,
    validate_labels,
)
from .lifecycle import MonitoringLifecycle
from .metrics import MonitoringMetrics
from .models import (
    HealthSnapshot,
    MetricPoint,
    MetricSnapshot,
)
from .prometheus import PrometheusRegistry
from .registry import MetricsRegistry
from .runtime import AsyncIOCollector, RuntimeCollector
from .scheduler import MonitoringScheduler
from .service import MonitoringService
from .sla import SLA, SLAReport
from .slo import SLO, SLOStatus
from .system import SystemCollector
from .telemetry import TelemetryService
from .tracing import MonitoringTracing

__all__ = [
    # Config
    "MonitoringConfig",
    # Registry
    "MetricsRegistry",
    "PrometheusRegistry",
    # Base Collector
    "MetricsCollector",
    "BaseCollector",
    "CollectorRunner",
    # Runtime/System Collectors
    "RuntimeCollector",
    "AsyncIOCollector",
    "SystemCollector",
    # Infrastructure Collectors
    "DatabaseCollector",
    "RedisCollector",
    "KafkaCollector",
    "StorageCollector",
    "ApplicationCollector",
    "BusinessCollector",
    # Exporter
    "MetricsExporter",
    "BaseExporter",
    "PrometheusExporter",
    # Health
    "MonitoringHealth",
    # Metrics Tracking
    "MonitoringMetrics",
    # Models
    "MetricPoint",
    "MetricSnapshot",
    "HealthSnapshot",
    # Labels
    "STANDARD_LABELS",
    "build_default_labels",
    "validate_labels",
    # Exceptions
    "MonitoringError",
    "CollectorError",
    "ExporterError",
    "RegistryError",
    "HealthCheckError",
    # Alert Models
    "AlertLevel",
    "AlertState",
    "AlertEvent",
    "AlertHistory",
    # Alert System
    "AlertEngine",
    "AlertRule",
    "AlertRuleSet",
    "RuleEvaluator",
    "AlertRouter",
    "AlertSuppression",
    "EscalationPolicy",
    # Notification Channels
    "NotificationChannel",
    "BaseChannel",
    "LogChannel",
    "WebhookChannel",
    "EmailChannel",
    "SlackChannel",
    "DingTalkChannel",
    "EnterpriseWeChatChannel",
    "PagerDutyChannel",
    # Dashboard Models
    "DashboardCategory",
    "PanelType",
    "DashboardPanel",
    "DashboardTemplate",
    # Dashboard Management
    "GrafanaDashboard",
    "DashboardProvisioner",
    "DASHBOARD_TEMPLATES",
    "get_template",
    "list_templates",
    "all_templates",
    # SLO / SLA
    "SLO",
    "SLOStatus",
    "SLA",
    "SLAReport",
    # Bootstrap & Service (Part 5.5)
    "MonitoringBootstrap",
    "MonitoringService",
    "MonitoringScheduler",
    "MonitoringLifecycle",
    "TelemetryService",
    "MonitoringTracing",
    # DI Container
    "DIContainer",
    "register_monitoring",
]
