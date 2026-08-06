"""Scheduler Platform Integration — connects the Distributed Scheduler to the ICYQuant platform.

This package provides adapters that bridge the scheduler with:
* Workflow Engine — dispatch scheduled jobs as workflows
* EventBus — publish/subscribe scheduler lifecycle events
* Service Mesh — service discovery, mTLS, traffic policy
* Configuration Center — hot-reload scheduler configs
* Feature Flags — canary/blue-green scheduling
* Business Domains — OMS, Risk, Execution, Settlement, Ledger
* AI & Research — strategy runtime, AI agents, research pipelines
* Dashboard API, SDK, CLI — developer & operator tooling
"""

from .integration_manager import SchedulerIntegrationManager, IntegrationState
from .platform_runtime import PlatformRuntime, PlatformRuntimePhase
from .scheduler_gateway import SchedulerGateway, GatewayMode

from .workflow_adapter import WorkflowAdapter, WorkflowAdapterState
from .workflow_bridge import WorkflowBridge, BridgeState
from .eventbus_adapter import EventBusAdapter, EventBusAdapterState

from .service_mesh_adapter import ServiceMeshAdapter, MeshMode
from .configuration_adapter import ConfigurationAdapter, ConfigSource
from .feature_flag_adapter import FeatureFlagAdapter, FlagEvaluation
from .discovery_adapter import DiscoveryAdapter, ServiceInstance
from .secrets_adapter import SecretsAdapter, SecretProvider

from .strategy_runtime_adapter import StrategyRuntimeAdapter, StrategyAdapterState
from .ai_runtime_adapter import AIRuntimeAdapter, AIAdapterState
from .research_runtime_adapter import ResearchRuntimeAdapter, ResearchAdapterState

from .market_data_adapter import MarketDataAdapter, MarketEventType
from .order_adapter import OrderAdapter, OrderAdapterState
from .risk_adapter import RiskAdapter, RiskAdapterState
from .execution_adapter import ExecutionAdapter, ExecutionAdapterState
from .settlement_adapter import SettlementAdapter, SettlementAdapterState
from .ledger_adapter import LedgerAdapter, LedgerAdapterState

from .notification_adapter import NotificationAdapter, NotificationChannel
from .webhook_adapter import WebhookAdapter, WebhookDelivery

from .dashboard_api import DashboardAPI, DashboardEndpoint
from .sdk import SchedulerSDK, SDKClient
from .cli import SchedulerCLI, CLICommand

from .metrics import IntegrationMetrics
from .telemetry import IntegrationTelemetry
from .telemetry_adapter import TelemetryAdapter, TelemetryProtocol
from .tracing_adapter import TracingAdapter, TraceContext
from .metrics_adapter import MetricsAdapter, MetricsSink
from .diagnostics import IntegrationDiagnostics
from .health import IntegrationHealth

__all__ = [
    # Core Platform
    "SchedulerIntegrationManager",
    "IntegrationState",
    "PlatformRuntime",
    "PlatformRuntimePhase",
    "SchedulerGateway",
    "GatewayMode",
    # Workflow & Event
    "WorkflowAdapter",
    "WorkflowAdapterState",
    "WorkflowBridge",
    "BridgeState",
    "EventBusAdapter",
    "EventBusAdapterState",
    # Infrastructure
    "ServiceMeshAdapter",
    "MeshMode",
    "ConfigurationAdapter",
    "ConfigSource",
    "FeatureFlagAdapter",
    "FlagEvaluation",
    "DiscoveryAdapter",
    "ServiceInstance",
    "SecretsAdapter",
    "SecretProvider",
    # Business Domains
    "StrategyRuntimeAdapter",
    "StrategyAdapterState",
    "AIRuntimeAdapter",
    "AIAdapterState",
    "ResearchRuntimeAdapter",
    "ResearchAdapterState",
    "MarketDataAdapter",
    "MarketEventType",
    "OrderAdapter",
    "OrderAdapterState",
    "RiskAdapter",
    "RiskAdapterState",
    "ExecutionAdapter",
    "ExecutionAdapterState",
    "SettlementAdapter",
    "SettlementAdapterState",
    "LedgerAdapter",
    "LedgerAdapterState",
    # Notification & Webhook
    "NotificationAdapter",
    "NotificationChannel",
    "WebhookAdapter",
    "WebhookDelivery",
    # Dashboard, SDK, CLI
    "DashboardAPI",
    "DashboardEndpoint",
    "SchedulerSDK",
    "SDKClient",
    "SchedulerCLI",
    "CLICommand",
    # Observability
    "IntegrationMetrics",
    "IntegrationTelemetry",
    "TelemetryAdapter",
    "TelemetryProtocol",
    "TracingAdapter",
    "TraceContext",
    "MetricsAdapter",
    "MetricsSink",
    "IntegrationDiagnostics",
    "IntegrationHealth",
]
