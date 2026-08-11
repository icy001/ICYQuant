"""AI Platform Integration — unified intelligent control layer for the ICYQuant platform.

The platform module serves as the unified entry point and control plane for all AI
operations, connecting the AI Agent subsystem with every other ICYQuant component
through standardized adapters and APIs.

Architecture:
    Gateway -> Control Plane -> Multi-Agent Runtime
        -> Model Router -> Provider Manager -> LLM
        -> Global Memory -> Context Manager
        -> Guardrail -> Audit -> Evaluation
        -> Platform Adapters -> Workflow/Research/OMS

Key principles:
    - Single control plane for all AI operations
    - Multi-model routing with automatic fallback
    - Cost and budget governance per user/project
    - Full audit trail for institutional compliance
    - Guardrail-driven safety with policy enforcement
    - REST, gRPC, and WebSocket APIs for all interaction modes
"""

from __future__ import annotations

# ── Core Platform ──
from services.ai_agent.platform.ai_platform import AIPlatform
from services.ai_agent.platform.control_plane import ControlPlane
from services.ai_agent.platform.gateway import AIGateway
from services.ai_agent.platform.lifecycle_manager import LifecycleManager
from services.ai_agent.platform.runtime_manager import RuntimeManager
from services.ai_agent.platform.session_orchestrator import SessionOrchestrator

# ── Memory & Context ──
from services.ai_agent.platform.global_memory_manager import GlobalMemoryManager
from services.ai_agent.platform.context_manager import ContextManager

# ── Model Routing ──
from services.ai_agent.platform.model_router import ModelRouter
from services.ai_agent.platform.model_registry import ModelRegistry
from services.ai_agent.platform.model_selector import ModelSelector
from services.ai_agent.platform.model_fallback import ModelFallback
from services.ai_agent.platform.provider_manager import ProviderManager

# ── Cost Management ──
from services.ai_agent.platform.token_manager import TokenManager
from services.ai_agent.platform.cost_manager import CostManager
from services.ai_agent.platform.budget_controller import BudgetController

# ── Governance ──
from services.ai_agent.platform.policy_engine import PolicyEngine
from services.ai_agent.platform.guardrail_engine import GuardrailEngine
from services.ai_agent.platform.audit_center import AuditCenter

# ── Observability & Evaluation ──
from services.ai_agent.platform.observability import PlatformObservability
from services.ai_agent.platform.trace_collector import TraceCollector
from services.ai_agent.platform.evaluation_engine import EvaluationEngine
from services.ai_agent.platform.benchmark_engine import BenchmarkEngine

# ── Platform Adapters ──
from services.ai_agent.platform.workflow_adapter import WorkflowAdapter
from services.ai_agent.platform.research_adapter import ResearchAdapter
from services.ai_agent.platform.scheduler_adapter import SchedulerAdapter
from services.ai_agent.platform.risk_adapter import RiskAdapter
from services.ai_agent.platform.oms_adapter import OMSAdapter
from services.ai_agent.platform.execution_adapter import ExecutionAdapter

# ── API Layer ──
from services.ai_agent.platform.rest_api import PlatformRESTAPI
from services.ai_agent.platform.grpc_api import PlatformgRPCAPI
from services.ai_agent.platform.websocket_gateway import WebSocketGateway
from services.ai_agent.platform.sdk import PlatformSDK

# ── Observability ──
from services.ai_agent.platform.metrics import PlatformMetrics
from services.ai_agent.platform.telemetry import PlatformTelemetry
from services.ai_agent.platform.diagnostics import PlatformDiagnostics
from services.ai_agent.platform.health import PlatformHealthChecker

__all__ = [
    # Core Platform
    "AIPlatform",
    "ControlPlane",
    "AIGateway",
    "LifecycleManager",
    "RuntimeManager",
    "SessionOrchestrator",
    # Memory & Context
    "GlobalMemoryManager",
    "ContextManager",
    # Model Routing
    "ModelRouter",
    "ModelRegistry",
    "ModelSelector",
    "ModelFallback",
    "ProviderManager",
    # Cost Management
    "TokenManager",
    "CostManager",
    "BudgetController",
    # Governance
    "PolicyEngine",
    "GuardrailEngine",
    "AuditCenter",
    # Observability & Evaluation
    "PlatformObservability",
    "TraceCollector",
    "EvaluationEngine",
    "BenchmarkEngine",
    # Platform Adapters
    "WorkflowAdapter",
    "ResearchAdapter",
    "SchedulerAdapter",
    "RiskAdapter",
    "OMSAdapter",
    "ExecutionAdapter",
    # API Layer
    "PlatformRESTAPI",
    "PlatformgRPCAPI",
    "WebSocketGateway",
    "PlatformSDK",
    # Observability
    "PlatformMetrics",
    "PlatformTelemetry",
    "PlatformDiagnostics",
    "PlatformHealthChecker",
]
