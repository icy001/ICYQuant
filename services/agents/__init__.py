"""AI Trading Agent & Autonomous Decision Engine.

Multi-agent system for autonomous quantitative trading:
- Market Agent: market observation and regime detection
- Trading Agent: trade proposal generation
- Risk Agent: risk review and approval
- Portfolio Agent: portfolio composition management
- Execution Agent: optimal trade execution
- Supervisor: AI investment committee coordinator
- Decision Engine: unified decision making
- Policy Engine: behavioral boundaries
- Workflow Engine: automated trading pipelines
"""

from .agent_base import (
    BaseAgent, AgentStatus, Observation, Analysis, Decision, DecisionAction,
)
from .market_agent import (
    MarketAgent, MarketRegime, TrendDirection, VolatilityLevel, LiquidityCondition,
)
from .trading_agent import TradingAgent
from .risk_agent import (
    RiskAgent, RiskDecision, RiskAssessment,
)
from .portfolio_agent import (
    PortfolioAgent, RebalanceProposal, RebalanceType,
)
from .execution_agent import (
    ExecutionAgent, ExecutionOrder, ExecutionStatus, ExecutionAlgorithm,
)
from .supervisor import (
    Supervisor, SystemMode, EscalationLevel, PipelineRun, SystemEvent,
)
from .communication import (
    AgentCommunicator,
)
from .memory import (
    AgentMemory, MemoryImportance, MemoryItem, MemoryType,
)
from .decision import (
    DecisionEngine, DecisionInput, DecisionOutput, FinalDecision,
)
from .policy import (
    PolicyEngine, PolicyRule, PolicyType, PolicyAction,
)
from .workflow import (
    WorkflowEngine, WorkflowStatus, StepStatus, WorkflowStep, WorkflowRun,
)
from .service import (
    AgentService, ServiceConfig, ServiceStatus,
)
from .api.agent_api import AgentAPI, APIResponse

__all__ = [
    # Base
    "BaseAgent", "AgentStatus", "Observation", "Analysis", "Decision", "DecisionAction",
    # Market Agent
    "MarketAgent", "MarketRegime", "TrendDirection", "VolatilityLevel", "LiquidityCondition",
    # Trading Agent
    "TradingAgent",
    # Risk Agent
    "RiskAgent", "RiskDecision", "RiskAssessment",
    # Portfolio Agent
    "PortfolioAgent", "RebalanceProposal", "RebalanceType",
    # Execution Agent
    "ExecutionAgent", "ExecutionOrder", "ExecutionStatus", "ExecutionAlgorithm",
    # Supervisor
    "Supervisor", "SystemMode", "EscalationLevel", "PipelineRun", "SystemEvent",
    # Communication
    "AgentCommunicator",
    # Memory
    "AgentMemory", "MemoryImportance", "MemoryItem", "MemoryType",
    # Decision Engine
    "DecisionEngine", "DecisionInput", "DecisionOutput", "FinalDecision",
    # Policy Engine
    "PolicyEngine", "PolicyRule", "PolicyType", "PolicyAction",
    # Workflow
    "WorkflowEngine", "WorkflowStatus", "StepStatus", "WorkflowStep", "WorkflowRun",
    # Service
    "AgentService", "ServiceConfig", "ServiceStatus",
    # API
    "AgentAPI", "APIResponse",
]
