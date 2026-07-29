"""Task Delegation Engine - intelligent task assignment to AI agents."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from collections import defaultdict

from .message import AgentIdentity, AgentRole, AgentMessage, MessagePriority


class TaskDomain(Enum):
    """Domain classification for tasks."""
    RESEARCH = "RESEARCH"
    STRATEGY = "STRATEGY"
    RISK = "RISK"
    PORTFOLIO = "PORTFOLIO"
    EXECUTION = "EXECUTION"
    PERFORMANCE = "PERFORMANCE"
    LEARNING = "LEARNING"
    MARKET = "MARKET"
    CAPITAL = "CAPITAL"
    CROSS_DOMAIN = "CROSS_DOMAIN"


class TaskStatus(Enum):
    """Status of a delegated task."""
    PENDING = "PENDING"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    DELEGATED = "DELEGATED"
    BLOCKED = "BLOCKED"


class DelegationStrategy(Enum):
    """Strategy for assigning tasks to agents."""
    CAPABILITY_MATCH = "CAPABILITY_MATCH"
    LOAD_BALANCE = "LOAD_BALANCE"
    EXPERTISE_PRIORITY = "EXPERTISE_PRIORITY"
    ROUND_ROBIN = "ROUND_ROBIN"
    RANDOM = "RANDOM"


@dataclass
class Task:
    """A task to be delegated."""
    task_id: str
    domain: TaskDomain
    description: str
    required_capabilities: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    priority: MessagePriority = MessagePriority.MEDIUM
    context: Dict[str, Any] = field(default_factory=dict)
    deadline: str = ""
    status: TaskStatus = TaskStatus.PENDING
    assigned_to: Optional[AgentIdentity] = None
    result: Dict[str, Any] = field(default_factory=dict)
    subtasks: List["Task"] = field(default_factory=list)

    def split(self, subtask_descriptions: List[Dict[str, Any]]) -> List["Task"]:
        """Split this task into subtasks."""
        subtasks = []
        for i, desc in enumerate(subtask_descriptions):
            sub = Task(
                task_id=f"{self.task_id}_sub_{i}",
                domain=TaskDomain(desc.get("domain", self.domain.value)),
                description=desc["description"],
                required_capabilities=desc.get("capabilities", []),
                priority=self.priority,
                context={**self.context, **desc.get("context", {})},
                dependencies=[self.task_id],
            )
            subtasks.append(sub)
        self.subtasks = subtasks
        return subtasks


@dataclass
class DelegationPlan:
    """Plan for delegating a complex task."""
    plan_id: str
    root_task: Task
    subtasks: List[Task] = field(default_factory=list)
    assignment: Dict[str, str] = field(default_factory=dict)
    execution_order: List[str] = field(default_factory=list)

    def get_next_tasks(self) -> List[Task]:
        """Get tasks ready for execution (dependencies met)."""
        completed = {t.task_id for t in self.subtasks if t.status == TaskStatus.COMPLETED}
        return [
            t for t in self.subtasks
            if t.status == TaskStatus.PENDING
            and all(dep in completed for dep in t.dependencies)
        ]


class TaskDelegationEngine:
    """Intelligent task delegation engine.

    Responsibilities:
    - Analyze task requirements
    - Match tasks to agent capabilities
    - Split complex tasks into subtasks
    - Track task execution status
    - Optimize delegation based on agent load and expertise
    """

    # Default capability mappings per agent role
    ROLE_CAPABILITIES: Dict[AgentRole, List[str]] = {
        AgentRole.RESEARCH: [
            "fundamental_analysis", "quant_research", "data_analysis",
            "market_research", "sentiment_analysis", "literature_review",
        ],
        AgentRole.STRATEGY: [
            "alpha_generation", "signal_research", "backtesting",
            "strategy_design", "factor_research",
        ],
        AgentRole.RISK: [
            "risk_analysis", "var_calculation", "stress_testing",
            "exposure_control", "drawdown_protection",
        ],
        AgentRole.PORTFOLIO: [
            "portfolio_construction", "position_sizing", "asset_allocation",
            "rebalancing", "optimization",
        ],
        AgentRole.EXECUTION: [
            "order_execution", "slippage_control", "timing_optimization",
            "market_impact", "execution_algorithm",
        ],
        AgentRole.PERFORMANCE: [
            "performance_analysis", "attribution", "benchmarking",
            "scorecard", "reporting",
        ],
        AgentRole.LEARNING: [
            "pattern_recognition", "model_training", "parameter_optimization",
            "reinforcement_learning", "knowledge_extraction",
        ],
        AgentRole.MARKET: [
            "market_monitoring", "regime_detection", "trend_analysis",
            "liquidity_analysis", "correlation_analysis",
        ],
        AgentRole.CAPITAL: [
            "capital_allocation", "cash_management", "fund_flows",
            "exposure_management",
        ],
    }

    DOMAIN_ROLE_MAPPING: Dict[TaskDomain, List[AgentRole]] = {
        TaskDomain.RESEARCH: [AgentRole.RESEARCH],
        TaskDomain.STRATEGY: [AgentRole.STRATEGY, AgentRole.RESEARCH],
        TaskDomain.RISK: [AgentRole.RISK],
        TaskDomain.PORTFOLIO: [AgentRole.PORTFOLIO, AgentRole.CAPITAL],
        TaskDomain.EXECUTION: [AgentRole.EXECUTION],
        TaskDomain.PERFORMANCE: [AgentRole.PERFORMANCE, AgentRole.LEARNING],
        TaskDomain.LEARNING: [AgentRole.LEARNING],
        TaskDomain.MARKET: [AgentRole.MARKET, AgentRole.RESEARCH],
        TaskDomain.CAPITAL: [AgentRole.CAPITAL, AgentRole.PORTFOLIO],
        TaskDomain.CROSS_DOMAIN: [AgentRole.CIO],
    }

    def __init__(self):
        self._agents: Dict[str, AgentIdentity] = {}
        self._tasks: Dict[str, Task] = {}
        self._agent_load: Dict[str, int] = defaultdict(int)
        self._plans: Dict[str, DelegationPlan] = {}

    def register_agent(self, agent: AgentIdentity, capabilities: List[str] = None):
        """Register an agent with its capabilities."""
        self._agents[agent.agent_id] = agent
        if capabilities:
            # Custom capabilities take precedence
            pass
        self._agent_load[agent.agent_id] = 0

    def delegate(self, task: Task, strategy: DelegationStrategy = DelegationStrategy.CAPABILITY_MATCH) -> Dict[str, Any]:
        """Delegate a task to the most suitable agent.

        Returns delegation result with assigned agent info.
        """
        suitable_agents = self._find_suitable_agents(task)

        if not suitable_agents:
            return {
                "assigned": task.description,
                "task_id": task.task_id,
                "assigned_to": None,
                "success": False,
                "reason": "No suitable agent found",
            }

        if strategy == DelegationStrategy.CAPABILITY_MATCH:
            assigned = self._capability_match(task, suitable_agents)
        elif strategy == DelegationStrategy.LOAD_BALANCE:
            assigned = self._load_balance(suitable_agents)
        elif strategy == DelegationStrategy.EXPERTISE_PRIORITY:
            assigned = self._expertise_priority(task, suitable_agents)
        elif strategy == DelegationStrategy.ROUND_ROBIN:
            assigned = self._round_robin(suitable_agents)
        else:
            import random
            assigned = random.choice(suitable_agents)

        task.assigned_to = assigned
        task.status = TaskStatus.ASSIGNED
        self._tasks[task.task_id] = task
        self._agent_load[assigned.agent_id] += 1

        return {
            "assigned": task.description,
            "task_id": task.task_id,
            "assigned_to": assigned.to_dict(),
            "success": True,
            "strategy": strategy.value,
        }

    def delegate_complex(self, root_task: Task, subtask_specs: List[Dict[str, Any]]) -> DelegationPlan:
        """Delegate a complex task by splitting it into subtasks.

        Example: An investment opportunity on NVDA:
        - Research Agent: analyze fundamentals
        - Strategy Agent: analyze trading opportunity
        - Risk Agent: analyze risk
        - Portfolio Agent: determine position size
        """
        subtasks = root_task.split(subtask_specs)
        assignment = {}
        execution_order = []

        for subtask in subtasks:
            result = self.delegate(subtask)
            if result["success"]:
                assignment[subtask.task_id] = result["assigned_to"]["agent_id"]
                execution_order.append(subtask.task_id)

        plan = DelegationPlan(
            plan_id=f"plan_{root_task.task_id}",
            root_task=root_task,
            subtasks=subtasks,
            assignment=assignment,
            execution_order=execution_order,
        )
        self._plans[plan.plan_id] = plan
        return plan

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get current status of a task."""
        task = self._tasks.get(task_id)
        if not task:
            return None
        return {
            "task_id": task.task_id,
            "status": task.status.value,
            "assigned_to": task.assigned_to.to_dict() if task.assigned_to else None,
            "result": task.result,
        }

    def complete_task(self, task_id: str, result: Dict[str, Any]):
        """Mark a task as completed with results."""
        task = self._tasks.get(task_id)
        if task:
            task.status = TaskStatus.COMPLETED
            task.result = result
            if task.assigned_to:
                self._agent_load[task.assigned_to.agent_id] = max(0, self._agent_load[task.assigned_to.agent_id] - 1)

    def get_agent_load(self) -> Dict[str, int]:
        """Get current task load per agent."""
        return dict(self._agent_load)

    def _find_suitable_agents(self, task: Task) -> List[AgentIdentity]:
        """Find agents suitable for a task based on domain and capabilities."""
        suitable_roles = self.DOMAIN_ROLE_MAPPING.get(task.domain, [])

        suitable = []
        for agent in self._agents.values():
            if agent.role in suitable_roles:
                suitable.append(agent)

        # Further filter by required capabilities
        if task.required_capabilities:
            filtered = []
            for agent in suitable:
                agent_caps = self.ROLE_CAPABILITIES.get(agent.role, []) + agent.capabilities
                if all(cap in agent_caps for cap in task.required_capabilities):
                    filtered.append(agent)
            suitable = filtered

        return suitable

    def _capability_match(self, task: Task, agents: List[AgentIdentity]) -> AgentIdentity:
        """Select agent with best capability match."""
        best_agent = agents[0]
        best_score = -1

        for agent in agents:
            caps = set(self.ROLE_CAPABILITIES.get(agent.role, []) + agent.capabilities)
            required = set(task.required_capabilities)
            if required:
                score = len(caps & required) / len(required)
            else:
                score = len(caps) * 0.1
            if score > best_score:
                best_score = score
                best_agent = agent

        return best_agent

    def _load_balance(self, agents: List[AgentIdentity]) -> AgentIdentity:
        """Select agent with lowest current load."""
        return min(agents, key=lambda a: self._agent_load.get(a.agent_id, 0))

    def _expertise_priority(self, task: Task, agents: List[AgentIdentity]) -> AgentIdentity:
        """Select agent with highest expertise for the task domain."""
        return max(agents, key=lambda a: len(self.ROLE_CAPABILITIES.get(a.role, [])))

    def _round_robin(self, agents: List[AgentIdentity]) -> AgentIdentity:
        """Select agent using round-robin."""
        total_assigned = sum(self._agent_load.values())
        idx = total_assigned % len(agents)
        return agents[idx]
