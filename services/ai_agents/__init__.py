"""
ICYQuant AI Agents — Multi-Agent Quant Collaboration Framework.

Provides a complete multi-agent system for quantitative research:
    - Core Runtime: agent lifecycle, scheduling, orchestration
    - Communication: message bus, routers, shared memory
    - Deliberation: debate, voting, consensus, decision engines
    - Specialized Agents: planner, researcher, factor, strategy,
      risk, portfolio, execution, reviewer, critic, coordinator
    - Safety: immutable guardrails, policy engine
    - Observability: metrics, telemetry, diagnostics, health probes

Key guarantees:
    - AI agents CANNOT directly execute trades (OMS-only path)
    - AI agents CANNOT bypass risk engine checks
    - All agent actions are logged for audit trail
    - Human-in-the-loop for all trading decisions
"""

__version__ = "0.4.0-alpha2"

# Core
from .agent_runtime import AgentRuntime, RuntimeConfig, RuntimeState, RuntimeStats
from .agent_registry import AgentRegistry, AgentInfo, AgentStatus
from .agent_manager import AgentManager
from .agent_state import AgentStateMachine, AgentStateType
from .agent_capability import Capability, CapabilityDomain, CAPABILITY_CATALOG
from .agent_context import AgentContext
from .agent_scheduler import AgentScheduler, ScheduledTask, TaskPriority, TaskStatus
from .agent_orchestrator import AgentOrchestrator, OrchestrationContext, OrchestrationPhase

# Communication
from .agent_message import (
    MessageEnvelope, MessageType, MessagePriority,
    TaskMessage, OpinionMessage, VoteMessage, ErrorMessage, MessageSerializer,
)
from .communication_bus import CommunicationBus, BusStats
from .message_router import MessageRouter, RouteRule, RouteStrategy, RouterStats
from .task_router import TaskRouter, DispatchResult, DispatchStrategy
from .tool_router import ToolRouter, ToolDefinition, ToolCategory, ToolPermission, ToolCall, ToolResult
from .memory_bus import MemoryBus, MemoryEntry, AccessLevel
from .shared_memory import SharedMemory, NamespaceStats

# Deliberation
from .debate_engine import DebateEngine, DebateResult, DebateFormat, DebateRole, DebatePhase
from .voting_engine import VotingEngine, VoteSession, VotingConfig, VotingStrategy, VoteDecision
from .consensus_engine import ConsensusEngine, ConsensusResult, ConsensusLevel
from .decision_engine import DecisionEngine, Decision, DecisionAction, DecisionDomain, DecisionContext
from .confidence_engine import ConfidenceEngine, ConfidenceScore, ConfidenceFactors, ConfidenceTier
from .evidence_manager import EvidenceManager, Evidence, EvidenceChain, EvidenceType, EvidenceStrength

# Specialized Agents
from .planner_agent import PlannerAgent, Plan, PlanStep, PlanStatus, PlanStepType
from .researcher_agent import ResearcherAgent, ResearchBrief, ResearchFinding
from .factor_agent import FactorAgent, FactorCandidate, FactorAnalysisReport
from .strategy_agent import StrategyAgent, StrategyCandidate, StrategyReport
from .risk_agent import RiskAgent, RiskAssessment, RiskLevel, RiskMetric
from .portfolio_agent import PortfolioAgent, PortfolioOptimization, Allocation
from .execution_agent import ExecutionAgent, ExecutionAdvice, ExecutionMonitor, ExecutionStatus
from .reviewer_agent import ReviewerAgent, ReviewReport, ReviewVerdict, ReviewIssue
from .critic_agent import CriticAgent, CritiqueReport, CritiquePoint, CritiqueSeverity
from .coordinator_agent import CoordinatorAgent, CoordinatorState, CoordinatedPhase

# Workflow
from .workflow_state import WorkflowState, WorkflowStatus
from .agent_workflow import WorkflowEngine, WorkflowDefinition, WorkflowTask, TaskType
from .result_aggregator import ResultAggregator, AggregatedResult, AggregationMode, ConflictRecord

# Safety
from .guardrail import GuardrailEngine, GuardrailCheck, GuardrailResult, GuardrailEvaluation, GuardrailAction, GuardrailDomain
from .policy_engine import PolicyEngine, Policy, PolicyEffect, PolicyScope, PolicyEvaluation

# Observability
from .metrics import AgentMetrics, MetricValue, MetricType
from .telemetry import AgentTelemetry, Span, SpanKind, SpanStatusCode, TraceContext
from .diagnostics import AgentDiagnostics, DiagnosticReport, DiagnosticFinding, DiagnosticSeverity, DiagnosticCategory
from .health import HealthProbe, HealthReport, HealthStatus, ComponentHealth

__all__ = [
    # Core
    "AgentRuntime", "RuntimeConfig", "RuntimeState", "RuntimeStats",
    "AgentRegistry", "AgentInfo", "AgentStatus",
    "AgentManager",
    "AgentStateMachine", "AgentStateType",
    "Capability", "CapabilityDomain", "CAPABILITY_CATALOG",
    "AgentContext",
    "AgentScheduler", "ScheduledTask", "TaskPriority", "TaskStatus",
    "AgentOrchestrator", "OrchestrationContext", "OrchestrationPhase",

    # Communication
    "MessageEnvelope", "MessageType", "MessagePriority",
    "TaskMessage", "OpinionMessage", "VoteMessage", "ErrorMessage",
    "MessageSerializer",
    "CommunicationBus", "BusStats",
    "MessageRouter", "RouteRule", "RouteStrategy", "RouterStats",
    "TaskRouter", "DispatchResult", "DispatchStrategy",
    "ToolRouter", "ToolDefinition", "ToolCategory", "ToolPermission", "ToolCall", "ToolResult",
    "MemoryBus", "MemoryEntry", "AccessLevel",
    "SharedMemory", "NamespaceStats",

    # Deliberation
    "DebateEngine", "DebateResult", "DebateFormat", "DebateRole", "DebatePhase",
    "VotingEngine", "VoteSession", "VotingConfig", "VotingStrategy", "VoteDecision",
    "ConsensusEngine", "ConsensusResult", "ConsensusLevel",
    "DecisionEngine", "Decision", "DecisionAction", "DecisionDomain", "DecisionContext",
    "ConfidenceEngine", "ConfidenceScore", "ConfidenceFactors", "ConfidenceTier",
    "EvidenceManager", "Evidence", "EvidenceChain", "EvidenceType", "EvidenceStrength",

    # Specialized Agents
    "PlannerAgent", "Plan", "PlanStep", "PlanStatus", "PlanStepType",
    "ResearcherAgent", "ResearchBrief", "ResearchFinding",
    "FactorAgent", "FactorCandidate", "FactorAnalysisReport",
    "StrategyAgent", "StrategyCandidate", "StrategyReport",
    "RiskAgent", "RiskAssessment", "RiskLevel", "RiskMetric",
    "PortfolioAgent", "PortfolioOptimization", "Allocation",
    "ExecutionAgent", "ExecutionAdvice", "ExecutionMonitor", "ExecutionStatus",
    "ReviewerAgent", "ReviewReport", "ReviewVerdict", "ReviewIssue",
    "CriticAgent", "CritiqueReport", "CritiquePoint", "CritiqueSeverity",
    "CoordinatorAgent", "CoordinatorState", "CoordinatedPhase",

    # Workflow
    "WorkflowState", "WorkflowStatus",
    "WorkflowEngine", "WorkflowDefinition", "WorkflowTask", "TaskType",
    "ResultAggregator", "AggregatedResult", "AggregationMode", "ConflictRecord",

    # Safety
    "GuardrailEngine", "GuardrailCheck", "GuardrailResult", "GuardrailEvaluation",
    "GuardrailAction", "GuardrailDomain",
    "PolicyEngine", "Policy", "PolicyEffect", "PolicyScope", "PolicyEvaluation",

    # Observability
    "AgentMetrics", "MetricValue", "MetricType",
    "AgentTelemetry", "Span", "SpanKind", "SpanStatusCode", "TraceContext",
    "AgentDiagnostics", "DiagnosticReport", "DiagnosticFinding", "DiagnosticSeverity", "DiagnosticCategory",
    "HealthProbe", "HealthReport", "HealthStatus", "ComponentHealth",
]
