"""Tool Calling Framework for AI Agent Platform.

Architecture:
    AI Agent -> Planning Engine -> Tool Selector -> Tool Router
        -> Permission -> Sandbox -> Executor
        -> Platform Tools (Workflow / Research / Risk / OMS)
        -> Observation & Reflection

The Tool Calling Framework connects the AI Agent to the entire ICYQuant
platform while ensuring safe, auditable tool execution.

Submodules:
    - Core: tool_definition, tool_metadata, tool_registry, tool_catalog
    - Discovery: tool_discovery, tool_selector, tool_router
    - Execution: tool_executor, tool_runtime, tool_context, tool_manager, tool_result
    - Security: tool_permission, tool_policy, tool_sandbox, tool_validator
    - Reliability: tool_cache, tool_retry, tool_recovery
    - Intelligence: observation_engine, reflection_engine, execution_trace
    - SDK: tool_sdk
    - Adapters: workflow_tools, research_tools, scheduler_tools,
                 market_data_tools, strategy_tools, portfolio_tools, risk_tools
    - Observability: diagnostics, metrics, telemetry, health
"""

from __future__ import annotations

# ── Core ──
from services.ai_agent.tooling.tool_definition import ToolDefinition, ToolInput, ToolOutput
from services.ai_agent.tooling.tool_metadata import ToolMetadata
from services.ai_agent.tooling.tool_registry import ToolRegistry
from services.ai_agent.tooling.tool_catalog import ToolCatalog, CatalogEntry

# ── Discovery ──
from services.ai_agent.tooling.tool_discovery import ToolDiscovery
from services.ai_agent.tooling.tool_selector import ToolSelector, CandidateTool
from services.ai_agent.tooling.tool_router import ToolRouter, RouteDecision

# ── Execution ──
from services.ai_agent.tooling.tool_executor import ToolExecutor
from services.ai_agent.tooling.tool_runtime import ToolRuntime, RuntimeConfig
from services.ai_agent.tooling.tool_context import ToolContext
from services.ai_agent.tooling.tool_manager import ToolManager
from services.ai_agent.tooling.tool_result import ToolResult

# ── Security ──
from services.ai_agent.tooling.tool_permission import ToolPermissionManager, Permission
from services.ai_agent.tooling.tool_policy import ToolPolicyEngine, Policy
from services.ai_agent.tooling.tool_sandbox import ToolSandbox, SandboxConfig
from services.ai_agent.tooling.tool_validator import ToolValidator

# ── Reliability ──
from services.ai_agent.tooling.tool_cache import ToolCache, CacheEntry
from services.ai_agent.tooling.tool_retry import ToolRetry, RetryPolicy
from services.ai_agent.tooling.tool_recovery import ToolRecovery, RecoveryPlan

# ── Intelligence ──
from services.ai_agent.tooling.observation_engine import ObservationEngine, Observation
from services.ai_agent.tooling.reflection_engine import ReflectionEngine, Reflection
from services.ai_agent.tooling.execution_trace import ExecutionTrace, TraceStep

# ── SDK ──
from services.ai_agent.tooling.tool_sdk import ToolSDK, tool

# ── Adapters ──
from services.ai_agent.tooling.workflow_tools import WorkflowTools
from services.ai_agent.tooling.research_tools import ResearchTools
from services.ai_agent.tooling.scheduler_tools import SchedulerTools
from services.ai_agent.tooling.market_data_tools import MarketDataTools
from services.ai_agent.tooling.strategy_tools import StrategyTools
from services.ai_agent.tooling.portfolio_tools import PortfolioTools
from services.ai_agent.tooling.risk_tools import RiskTools

# ── Observability ──
from services.ai_agent.tooling.diagnostics import ToolDiagnostics
from services.ai_agent.tooling.metrics import ToolMetrics
from services.ai_agent.tooling.telemetry import ToolTelemetry
from services.ai_agent.tooling.health import ToolHealthChecker

__all__ = [
    # Core
    "ToolDefinition",
    "ToolInput",
    "ToolOutput",
    "ToolMetadata",
    "ToolRegistry",
    "ToolCatalog",
    "CatalogEntry",
    # Discovery
    "ToolDiscovery",
    "ToolSelector",
    "CandidateTool",
    "ToolRouter",
    "RouteDecision",
    # Execution
    "ToolExecutor",
    "ToolRuntime",
    "RuntimeConfig",
    "ToolContext",
    "ToolManager",
    "ToolResult",
    # Security
    "ToolPermissionManager",
    "Permission",
    "ToolPolicyEngine",
    "Policy",
    "ToolSandbox",
    "SandboxConfig",
    "ToolValidator",
    # Reliability
    "ToolCache",
    "CacheEntry",
    "ToolRetry",
    "RetryPolicy",
    "ToolRecovery",
    "RecoveryPlan",
    # Intelligence
    "ObservationEngine",
    "Observation",
    "ReflectionEngine",
    "Reflection",
    "ExecutionTrace",
    "TraceStep",
    # SDK
    "ToolSDK",
    "tool",
    # Adapters
    "WorkflowTools",
    "ResearchTools",
    "SchedulerTools",
    "MarketDataTools",
    "StrategyTools",
    "PortfolioTools",
    "RiskTools",
    # Observability
    "ToolDiagnostics",
    "ToolMetrics",
    "ToolTelemetry",
    "ToolHealthChecker",
]
