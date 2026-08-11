"""Collaboration — multi-agent collaboration framework for ICYQuant AI Agent Platform.

Pipeline:
    User Goal
        -> Coordinator Agent
        -> Task Graph (task_planner + dependency_graph)
        -> Agent Discovery + Agent Router
        -> Agent Execution (specialized agents)
        -> Message Bus (inter-agent communication)
        -> Shared Memory / Blackboard (context sharing)
        -> Consensus Engine (multi-agent decision)
        -> Conflict Resolver (disagreement resolution)
        -> Result

Provides:
    - Coordinator Agent: unified task orchestration
    - Agent Registry / Discovery / Router: dynamic agent management
    - Message Bus: pub/sub, request/response, broadcast, stream
    - Shared Memory + Blackboard: inter-agent context sharing
    - Task Graph + Dependency Graph: DAG-based task decomposition
    - Consensus Engine + Voting Engine: multi-agent decision making
    - Conflict Resolver + Negotiation Engine: disagreement handling
    - Specialized Agents: market, research, factor, strategy, portfolio, risk, execution, news, macro, reporting
    - Agent Monitor + Health: runtime supervision and auto-recovery
    - Agent SDK: plugin-based agent extension framework
"""

from __future__ import annotations

# ── Core Framework ──
from services.ai_agent.collaboration.collaboration_manager import (
    CollaborationManager,
)
from services.ai_agent.collaboration.collaboration_runtime import (
    CollaborationRuntime,
    RuntimeConfig,
)

# ── Coordinator ──
from services.ai_agent.collaboration.coordinator_agent import (
    CoordinatorAgent,
    CoordinationPlan,
    CoordinationResult,
)

# ── Agent Management ──
from services.ai_agent.collaboration.agent_registry import (
    AgentRegistry,
    AgentRegistration,
)
from services.ai_agent.collaboration.agent_directory import (
    AgentDirectory,
    DirectoryEntry,
)
from services.ai_agent.collaboration.agent_discovery import (
    AgentDiscovery,
    DiscoveryQuery,
    DiscoveryResult,
)
from services.ai_agent.collaboration.agent_router import (
    AgentRouter,
    RouteRequest,
    RouteDecision,
)
from services.ai_agent.collaboration.agent_scheduler import (
    AgentScheduler,
    ScheduleRequest,
    SchedulePlan,
)
from services.ai_agent.collaboration.agent_dispatcher import (
    AgentDispatcher,
    DispatchTask,
    DispatchResult,
)

# ── Messaging ──
from services.ai_agent.collaboration.message_bus import (
    MessageBus,
    Message,
    MessageEnvelope,
    Subscription,
)
from services.ai_agent.collaboration.message_router import (
    MessageRouter,
    RoutingRule,
)
from services.ai_agent.collaboration.message_queue import (
    MessageQueue,
    QueueItem,
    QueueStats,
)
from services.ai_agent.collaboration.event_bridge import (
    EventBridge,
    BridgeEvent,
)

# ── Shared Context ──
from services.ai_agent.collaboration.shared_memory import (
    SharedMemory,
    MemorySegment,
    MemoryQuery,
)
from services.ai_agent.collaboration.blackboard import (
    Blackboard,
    BlackboardEntry,
    BlackboardQuery,
)

# ── Task System ──
from services.ai_agent.collaboration.task_graph import (
    TaskGraph,
    TaskNode,
    TaskEdge,
)
from services.ai_agent.collaboration.task_planner import (
    TaskPlanner,
    PlanRequest,
    PlanResult,
)
from services.ai_agent.collaboration.dependency_graph import (
    DependencyGraph,
    DependencyNode,
    DependencyEdge,
)

# ── Decision System ──
from services.ai_agent.collaboration.consensus_engine import (
    ConsensusEngine,
    ConsensusProposal,
    ConsensusResult,
)
from services.ai_agent.collaboration.voting_engine import (
    VotingEngine,
    Vote,
    VotingResult,
)
from services.ai_agent.collaboration.conflict_resolver import (
    ConflictResolver,
    Conflict,
    Resolution,
)
from services.ai_agent.collaboration.negotiation_engine import (
    NegotiationEngine,
    Proposal,
    CounterProposal,
    NegotiationResult,
)

# ── Specialized Agents ──
from services.ai_agent.collaboration.market_agent import MarketAgent
from services.ai_agent.collaboration.research_agent import ResearchAgent
from services.ai_agent.collaboration.factor_agent import FactorAgent
from services.ai_agent.collaboration.strategy_agent import StrategyAgent
from services.ai_agent.collaboration.portfolio_agent import PortfolioAgent
from services.ai_agent.collaboration.risk_agent import RiskAgent
from services.ai_agent.collaboration.execution_agent import ExecutionAgent
from services.ai_agent.collaboration.news_agent import NewsAgent
from services.ai_agent.collaboration.macro_agent import MacroAgent
from services.ai_agent.collaboration.reporting_agent import ReportingAgent

# ── Monitor & Observability ──
from services.ai_agent.collaboration.agent_monitor import AgentMonitor, MonitorReport
from services.ai_agent.collaboration.agent_health import AgentHealthChecker, HealthStatus
from services.ai_agent.collaboration.agent_metrics import AgentMetrics
from services.ai_agent.collaboration.telemetry import CollaborationTelemetry
from services.ai_agent.collaboration.diagnostics import CollaborationDiagnostics
from services.ai_agent.collaboration.health import CollaborationHealthChecker

# ── SDK ──
from services.ai_agent.collaboration.sdk import AgentSDK, agent, AgentDefinition

__all__ = [
    # Core Framework
    "CollaborationManager",
    "CollaborationRuntime",
    "RuntimeConfig",
    # Coordinator
    "CoordinatorAgent",
    "CoordinationPlan",
    "CoordinationResult",
    # Agent Management
    "AgentRegistry",
    "AgentRegistration",
    "AgentDirectory",
    "DirectoryEntry",
    "AgentDiscovery",
    "DiscoveryQuery",
    "DiscoveryResult",
    "AgentRouter",
    "RouteRequest",
    "RouteDecision",
    "AgentScheduler",
    "ScheduleRequest",
    "SchedulePlan",
    "AgentDispatcher",
    "DispatchTask",
    "DispatchResult",
    # Messaging
    "MessageBus",
    "Message",
    "MessageEnvelope",
    "Subscription",
    "MessageRouter",
    "RoutingRule",
    "MessageQueue",
    "QueueItem",
    "QueueStats",
    "EventBridge",
    "BridgeEvent",
    # Shared Context
    "SharedMemory",
    "MemorySegment",
    "MemoryQuery",
    "Blackboard",
    "BlackboardEntry",
    "BlackboardQuery",
    # Task System
    "TaskGraph",
    "TaskNode",
    "TaskEdge",
    "TaskPlanner",
    "PlanRequest",
    "PlanResult",
    "DependencyGraph",
    "DependencyNode",
    "DependencyEdge",
    # Decision System
    "ConsensusEngine",
    "ConsensusProposal",
    "ConsensusResult",
    "VotingEngine",
    "Vote",
    "VotingResult",
    "ConflictResolver",
    "Conflict",
    "Resolution",
    "NegotiationEngine",
    "Proposal",
    "CounterProposal",
    "NegotiationResult",
    # Specialized Agents
    "MarketAgent",
    "ResearchAgent",
    "FactorAgent",
    "StrategyAgent",
    "PortfolioAgent",
    "RiskAgent",
    "ExecutionAgent",
    "NewsAgent",
    "MacroAgent",
    "ReportingAgent",
    # Monitor & Observability
    "AgentMonitor",
    "MonitorReport",
    "AgentHealthChecker",
    "HealthStatus",
    "AgentMetrics",
    "CollaborationTelemetry",
    "CollaborationDiagnostics",
    "CollaborationHealthChecker",
    # SDK
    "AgentSDK",
    "agent",
    "AgentDefinition",
]
