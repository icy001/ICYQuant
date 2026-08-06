"""Integration — unified research platform integration layer.

Commit 11 Part 1.5: Unified Research Platform Integration

This module bridges the Research Platform with ICYQuant's infrastructure:
Workflow Engine, Distributed Scheduler, EventBus, Strategy Runtime,
Market Data, Feature Store, Model Registry, and AI Runtime.

Exports::

    from services.research.integration import (
        ResearchIntegrationManager,
        PlatformRuntime,
        WorkflowAdapter,
        SchedulerAdapter,
        EventBusAdapter,
        StrategyRuntimeAdapter,
        ExecutionAdapter,
        MarketDataAdapter,
        FeatureStoreAdapter,
        ModelRegistry,
        ModelVersion,
        ModelArtifact,
        ModelDeployment,
        ExperimentAPI,
        DatasetAPI,
        FactorAPI,
        BacktestAPI,
        PortfolioAPI,
        AIRuntimeAdapter,
        LLMAdapter,
        AgentAdapter,
        NotebookRuntime,
        ReportCenter,
        DashboardAPI,
        ResearchSDK,
        ResearchCLI,
        IntegrationMetrics,
        IntegrationTracer,
        IntegrationDiagnostics,
        IntegrationHealthCheck,
    )
"""

from .integration_manager import ResearchIntegrationManager, PlatformState
from .platform_runtime import PlatformRuntime, PlatformRuntimeState
from .workflow_adapter import WorkflowAdapter, WorkflowAdapterState
from .scheduler_adapter import SchedulerAdapter, SchedulerAdapterState
from .eventbus_adapter import EventBusAdapter, EventBusAdapterState
from .strategy_runtime_adapter import StrategyRuntimeAdapter, StrategyRuntimeAdapterState
from .execution_adapter import ExecutionAdapter, ExecutionAdapterState
from .market_data_adapter import MarketDataAdapter, MarketDataAdapterState
from .feature_store_adapter import FeatureStoreAdapter, FeatureStoreAdapterState
from .model_registry import ModelRegistry, ModelRegistryState
from .model_version import ModelVersion, ModelVersionState
from .model_artifact import ModelArtifact, ModelArtifactState
from .model_deployment import ModelDeployment, ModelDeploymentState
from .experiment_api import ExperimentAPI
from .dataset_api import DatasetAPI
from .factor_api import FactorAPI
from .backtest_api import BacktestAPI
from .portfolio_api import PortfolioAPI
from .ai_runtime_adapter import AIRuntimeAdapter, AIRuntimeAdapterState
from .llm_adapter import LLMAdapter, LLMAdapterState
from .agent_adapter import AgentAdapter, AgentAdapterState
from .notebook_runtime import NotebookRuntime, NotebookRuntimeState
from .report_center import ReportCenter, ReportCenterState
from .dashboard_api import DashboardAPI
from .sdk import ResearchSDK
from .cli import ResearchCLI
from .metrics import IntegrationMetrics
from .telemetry import IntegrationTracer, IntegrationSpan, IntegrationSpanContext
from .diagnostics import IntegrationDiagnostics, IntegrationDiagnosticReport
from .health import IntegrationHealthCheck

__all__ = [
    # Core
    "ResearchIntegrationManager",
    "PlatformState",
    "PlatformRuntime",
    "PlatformRuntimeState",
    # Adapters
    "WorkflowAdapter",
    "WorkflowAdapterState",
    "SchedulerAdapter",
    "SchedulerAdapterState",
    "EventBusAdapter",
    "EventBusAdapterState",
    "StrategyRuntimeAdapter",
    "StrategyRuntimeAdapterState",
    "ExecutionAdapter",
    "ExecutionAdapterState",
    "MarketDataAdapter",
    "MarketDataAdapterState",
    "FeatureStoreAdapter",
    "FeatureStoreAdapterState",
    # Model Registry
    "ModelRegistry",
    "ModelRegistryState",
    "ModelVersion",
    "ModelVersionState",
    "ModelArtifact",
    "ModelArtifactState",
    "ModelDeployment",
    "ModelDeploymentState",
    # APIs
    "ExperimentAPI",
    "DatasetAPI",
    "FactorAPI",
    "BacktestAPI",
    "PortfolioAPI",
    # AI Runtime
    "AIRuntimeAdapter",
    "AIRuntimeAdapterState",
    "LLMAdapter",
    "LLMAdapterState",
    "AgentAdapter",
    "AgentAdapterState",
    "NotebookRuntime",
    "NotebookRuntimeState",
    # Report & Dashboard
    "ReportCenter",
    "ReportCenterState",
    "DashboardAPI",
    # SDK / CLI
    "ResearchSDK",
    "ResearchCLI",
    # Observability
    "IntegrationMetrics",
    "IntegrationTracer",
    "IntegrationSpan",
    "IntegrationSpanContext",
    "IntegrationDiagnostics",
    "IntegrationDiagnosticReport",
    "IntegrationHealthCheck",
]
