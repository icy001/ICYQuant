"""Workflow Platform Integration — service mesh, event bus, business domain and AI runtime adapters.

This package bridges the Workflow Engine with the broader ICYQuant platform,
making it the unified business orchestration core.

Modules::

    integration_manager      — unified lifecycle for all adapters
    platform_runtime         — shared execution substrate
    service_mesh_adapter     — service mesh (discovery, mTLS, traffic)
    eventbus_adapter         — event-driven workflow integration
    scheduler_adapter        — cron / interval / calendar workflow triggers
    configuration_adapter    — dynamic config with hot reload
    feature_flag_adapter     — feature flags for canary / blue-green
    discovery_adapter        — service discovery integration
    secrets_adapter          — secrets & credentials management
    telemetry_adapter        — unified telemetry bridge
    metrics_adapter          — metrics export bridge
    logging_adapter          — structured logging bridge
    tracing_adapter          — distributed tracing bridge
    strategy_runtime_adapter — trading strategy pipeline orchestration
    ai_runtime_adapter       — AI / LLM reasoning workflow orchestration
    order_adapter            — OMS order management
    risk_adapter             — risk check integration
    execution_adapter        — trade execution integration
    settlement_adapter       — settlement & clearing integration
    ledger_adapter           — ledger & accounting integration
    notification_adapter     — email / webhook / chat notifications
    sdk                      — Python SDK for workflow interaction
    cli                      — CLI for dev / test / ops
    api                      — unified management API
    webhook                  — external system webhook bridge
    metrics                  — platform integration metrics
    telemetry                — platform integration telemetry
    diagnostics              — platform integration diagnostics
    health                   — aggregated health checking
"""

from .integration_manager import WorkflowIntegrationManager, IntegrationState
from .platform_runtime import PlatformRuntime, PlatformRuntimeState, RuntimeContext
from .service_mesh_adapter import ServiceMeshAdapter
from .eventbus_adapter import EventBusAdapter
from .scheduler_adapter import SchedulerAdapter, ScheduleType
from .configuration_adapter import ConfigurationAdapter
from .feature_flag_adapter import FeatureFlagAdapter, FlagScope
from .discovery_adapter import DiscoveryAdapter
from .secrets_adapter import SecretsAdapter
from .telemetry_adapter import TelemetryAdapter
from .metrics_adapter import MetricsAdapter
from .logging_adapter import LoggingAdapter
from .tracing_adapter import TracingAdapter
from .strategy_runtime_adapter import StrategyRuntimeAdapter
from .ai_runtime_adapter import AIRuntimeAdapter, AIAction
from .order_adapter import OrderAdapter, OrderRequest
from .risk_adapter import RiskAdapter, RiskAssessment
from .execution_adapter import ExecutionAdapter, ExecutionReport
from .settlement_adapter import SettlementAdapter
from .ledger_adapter import LedgerAdapter
from .notification_adapter import NotificationAdapter, NotificationChannel
from .sdk import WorkflowSDK, WorkflowClient
from .cli import WorkflowCLI
from .api import PlatformAPI
from .webhook import WebhookManager, WebhookEventType
from .metrics import IntegrationMetrics
from .telemetry import IntegrationTelemetry
from .diagnostics import IntegrationDiagnostics
from .health import IntegrationHealthChecker

__all__ = [
    # Core
    "WorkflowIntegrationManager",
    "IntegrationState",
    "PlatformRuntime",
    "PlatformRuntimeState",
    "RuntimeContext",
    # Infrastructure
    "ServiceMeshAdapter",
    "EventBusAdapter",
    "SchedulerAdapter",
    "ScheduleType",
    "ConfigurationAdapter",
    "FeatureFlagAdapter",
    "FlagScope",
    "DiscoveryAdapter",
    "SecretsAdapter",
    # Observability adapters
    "TelemetryAdapter",
    "MetricsAdapter",
    "LoggingAdapter",
    "TracingAdapter",
    # AI / Strategy
    "StrategyRuntimeAdapter",
    "AIRuntimeAdapter",
    "AIAction",
    # Business domain
    "OrderAdapter",
    "OrderRequest",
    "RiskAdapter",
    "RiskAssessment",
    "ExecutionAdapter",
    "ExecutionReport",
    "SettlementAdapter",
    "LedgerAdapter",
    "NotificationAdapter",
    "NotificationChannel",
    # SDK / CLI / API
    "WorkflowSDK",
    "WorkflowClient",
    "WorkflowCLI",
    "PlatformAPI",
    "WebhookManager",
    "WebhookEventType",
    # Observability
    "IntegrationMetrics",
    "IntegrationTelemetry",
    "IntegrationDiagnostics",
    "IntegrationHealthChecker",
]
