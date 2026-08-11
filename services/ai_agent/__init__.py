"""
ICYQuant AI Agent Platform Foundation.

Provides unified intelligent decision-making entry point for the ICYQuant platform,
with planning, reasoning, memory, and workflow execution capabilities.

Architecture:
    User Request → Planning → Reasoning → Execution → Response

Modules:
    - agent_engine:      Unified agent entry point
    - agent_manager:     Agent lifecycle management
    - agent_runtime:     Runtime configuration and execution environment
    - agent_context:     Agent execution context
    - agent_registry:    Agent registration and discovery
    - agent_repository:  Agent state persistence
    - agent_factory:     Agent creation factory
    - agent_service:     Main service orchestrator
    - planner:           Goal-oriented planning engine
    - reasoning_engine:  Multi-mode reasoning engine
    - task_scheduler:    Task scheduling and dispatch
    - workflow_executor: Plan-to-execution workflow
    - session_manager:   Multi-agent session management
    - memory:            Hierarchical memory system
    - prompt:            Prompt lifecycle management
    - api:               REST API endpoints
    - metrics:           Prometheus metrics
    - telemetry:         Distributed tracing
    - diagnostics:       Diagnostics utilities
    - health:            Health check integration
"""

from __future__ import annotations

# ── Core Engine ──
from services.ai_agent.agent_engine import AgentEngine
from services.ai_agent.agent_manager import AgentManager
from services.ai_agent.agent_runtime import AgentRuntime, RuntimeConfig
from services.ai_agent.agent_context import AgentContext, ExecutionContext
from services.ai_agent.agent_registry import AgentRegistry
from services.ai_agent.agent_repository import AgentRepository
from services.ai_agent.agent_factory import AgentFactory
from services.ai_agent.agent_service import AgentService

# ── Planning & Reasoning ──
from services.ai_agent.planner import Planner, Plan, PlanStep
from services.ai_agent.reasoning_engine import ReasoningEngine, ReasoningResult
from services.ai_agent.task_scheduler import TaskScheduler
from services.ai_agent.workflow_executor import WorkflowExecutor

# ── Session ──
from services.ai_agent.session_manager import SessionManager, Session

# ── Sub-packages ──
from services.ai_agent import memory
from services.ai_agent import prompt

# ── Observability ──
from services.ai_agent.api import AgentAPI
from services.ai_agent.metrics import AgentMetrics
from services.ai_agent.telemetry import AgentTelemetry
from services.ai_agent.diagnostics import AgentDiagnostics
from services.ai_agent.health import AgentHealthChecker

__all__ = [
    # Core Engine
    "AgentEngine",
    "AgentManager",
    "AgentRuntime",
    "RuntimeConfig",
    "AgentContext",
    "ExecutionContext",
    "AgentRegistry",
    "AgentRepository",
    "AgentFactory",
    "AgentService",
    # Planning & Reasoning
    "Planner",
    "Plan",
    "PlanStep",
    "ReasoningEngine",
    "ReasoningResult",
    "TaskScheduler",
    "WorkflowExecutor",
    # Session
    "SessionManager",
    "Session",
    # Sub-packages
    "memory",
    "prompt",
    # Observability
    "AgentAPI",
    "AgentMetrics",
    "AgentTelemetry",
    "AgentDiagnostics",
    "AgentHealthChecker",
]
