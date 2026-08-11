"""Coordinator Agent — unified orchestration of the multi-agent collaboration pipeline.

Pipeline:
    User Goal
        -> CoordinatorAgent.plan() (decompose goal into tasks)
        -> TaskGraph (build DAG of subtasks)
        -> AgentDiscovery (find capable agents)
        -> AgentRouter (assign tasks to agents)
        -> AgentScheduler (prioritize and sequence)
        -> AgentDispatcher (execute tasks)
        -> MessageBus (coordinate inter-agent communication)
        -> SharedMemory / Blackboard (share context)
        -> ConsensusEngine (resolve multi-agent decisions)
        -> CoordinatorAgent.finalize() (aggregate results)
        -> CoordinationResult (final output)
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from services.ai_agent.collaboration.agent_registry import (
    AgentRegistration,
    AgentRegistry,
    AgentStatus,
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
    RouteStrategy,
)
from services.ai_agent.collaboration.agent_scheduler import (
    AgentScheduler,
    ScheduleRequest,
    TaskPriority,
)
from services.ai_agent.collaboration.agent_dispatcher import (
    AgentDispatcher,
    DispatchTask,
    DispatchResult,
)
from services.ai_agent.collaboration.message_bus import MessageBus
from services.ai_agent.collaboration.shared_memory import SharedMemory
from services.ai_agent.collaboration.blackboard import Blackboard
from services.ai_agent.collaboration.consensus_engine import (
    ConsensusEngine,
    ConsensusProposal,
    ConsensusResult,
)
from services.ai_agent.collaboration.task_graph import TaskGraph, TaskNode
from services.ai_agent.collaboration.task_planner import (
    TaskPlanner,
    PlanRequest,
    PlanResult,
)

logger = logging.getLogger(__name__)


class CoordinationStatus(str, Enum):
    """Status of a coordination cycle."""
    PLANNING = "planning"
    DISCOVERING = "discovering"
    ROUTING = "routing"
    SCHEDULING = "scheduling"
    EXECUTING = "executing"
    CONSENSUS = "consensus"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class CoordinationPlan:
    """A plan produced by the Coordinator for a user goal.

    Attributes:
        plan_id: Unique plan identifier.
        goal: The original user goal.
        subtasks: Decomposed subtasks.
        task_graph: DAG of task dependencies.
        agent_assignments: Mapping of tasks to assigned agents.
        created_at: Plan creation timestamp.
    """

    plan_id: str = ""
    goal: str = ""
    subtasks: List[Dict[str, Any]] = field(default_factory=list)
    task_graph: Optional[TaskGraph] = None
    agent_assignments: Dict[str, str] = field(default_factory=dict)
    created_at: float = field(default_factory=time.monotonic)

    def to_dict(self) -> Dict[str, Any]:
        """Return plan as a dictionary."""
        return {
            "plan_id": self.plan_id,
            "goal": self.goal,
            "subtask_count": len(self.subtasks),
            "agent_assignments": self.agent_assignments,
        }


@dataclass
class CoordinationResult:
    """Final result of a coordination cycle.

    Attributes:
        plan_id: The coordination plan ID.
        goal: The original user goal.
        status: Final coordination status.
        results: Dispatch results from all agents.
        consensus: Consensus result if applicable.
        duration_ms: Total coordination duration.
        summary: Human-readable summary.
    """

    plan_id: str = ""
    goal: str = ""
    status: CoordinationStatus = CoordinationStatus.PLANNING
    results: List[DispatchResult] = field(default_factory=list)
    consensus: Optional[ConsensusResult] = None
    duration_ms: float = 0.0
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Return result as a dictionary."""
        return {
            "plan_id": self.plan_id,
            "goal": self.goal,
            "status": self.status.value,
            "result_count": len(self.results),
            "consensus": self.consensus.to_dict() if self.consensus else None,
            "duration_ms": self.duration_ms,
            "summary": self.summary,
        }


class CoordinatorAgent:
    """Unified orchestrator for the multi-agent collaboration pipeline.

    The Coordinator Agent is the central entry point for all multi-agent
    operations. It receives a user goal, decomposes it into subtasks,
    discovers and assigns appropriate agents, orchestrates their execution,
    and aggregates results through consensus.

    Supports:
        - Goal decomposition into task graphs
        - Agent discovery and assignment
        - Execution orchestration (serial/parallel)
        - Inter-agent coordination via MessageBus
        - Consensus-driven decision making
        - Result aggregation and summarization

    Usage:
        coordinator = CoordinatorAgent(registry, discovery, router, ...)
        await coordinator.initialize()
        result = await coordinator.coordinate("Analyze market and generate report")
    """

    def __init__(
        self,
        registry: AgentRegistry,
        discovery: AgentDiscovery,
        router: AgentRouter,
        scheduler: AgentScheduler,
        dispatcher: AgentDispatcher,
        message_bus: MessageBus,
        shared_memory: SharedMemory,
        blackboard: Blackboard,
        consensus_engine: ConsensusEngine,
    ) -> None:
        """Initialize the Coordinator Agent with all subsystems.

        Args:
            registry: Agent registry for agent data.
            discovery: Agent discovery for finding capable agents.
            router: Agent router for task-to-agent assignment.
            scheduler: Agent scheduler for priority-based execution.
            dispatcher: Agent dispatcher for task execution.
            message_bus: Message bus for inter-agent communication.
            shared_memory: Shared memory for context sharing.
            blackboard: Blackboard for knowledge sharing.
            consensus_engine: Consensus engine for multi-agent decisions.
        """
        self._registry: AgentRegistry = registry
        self._discovery: AgentDiscovery = discovery
        self._router: AgentRouter = router
        self._scheduler: AgentScheduler = scheduler
        self._dispatcher: AgentDispatcher = dispatcher
        self._message_bus: MessageBus = message_bus
        self._shared_memory: SharedMemory = shared_memory
        self._blackboard: Blackboard = blackboard
        self._consensus_engine: ConsensusEngine = consensus_engine
        self._task_planner: Optional[TaskPlanner] = None

        self._initialized: bool = False
        self._active_plans: Dict[str, CoordinationPlan] = {}
        self._completed_results: Dict[str, CoordinationResult] = {}
        logger.info("CoordinatorAgent created")

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize the coordinator and its task planner."""
        if self._initialized:
            logger.warning("CoordinatorAgent already initialized")
            return

        self._task_planner = TaskPlanner()
        await self._task_planner.initialize()
        self._initialized = True
        logger.info("CoordinatorAgent initialized")

    async def shutdown(self) -> None:
        """Shut down the coordinator."""
        if not self._initialized:
            return
        if self._task_planner:
            await self._task_planner.shutdown()
        self._active_plans.clear()
        self._completed_results.clear()
        self._initialized = False
        logger.info("CoordinatorAgent shutdown complete")

    # ── Coordination ──

    async def coordinate(self, goal: str, context: Optional[Dict[str, Any]] = None) -> CoordinationResult:
        """Orchestrate the full multi-agent pipeline for a user goal.

        Pipeline: Plan → Discover → Route → Schedule → Execute → Consensus → Finalize

        Args:
            goal: The user goal in natural language.
            context: Optional additional context.

        Returns:
            CoordinationResult with aggregated outputs.
        """
        if not self._initialized:
            raise RuntimeError("CoordinatorAgent not initialized")

        started_at = time.monotonic()
        plan_id = uuid.uuid4().hex[:12]
        logger.info("Coordinating goal [%s]: %s", plan_id, goal)

        try:
            # Phase 1: Plan — decompose goal into tasks
            plan = await self.plan(goal, context)
            plan.plan_id = plan_id
            self._active_plans[plan_id] = plan

            # Phase 2: Discover agents for each subtask
            agent_assignments = await self._discover_agents(plan)

            # Phase 3: Route tasks to agents
            decisions = await self._route_tasks(plan, agent_assignments)

            # Phase 4: Schedule and execute
            results = await self._execute_tasks(decisions)

            # Phase 5: Reach consensus if multiple agents produced results
            consensus = None
            if len(results) > 1 and self._consensus_engine:
                consensus = await self._reach_consensus(results, goal)

            # Phase 6: Finalize
            result = await self.finalize(plan_id, results, consensus)
            self._completed_results[plan_id] = result

            return result

        except Exception as e:
            logger.exception("Coordination failed for [%s]", plan_id)
            result = CoordinationResult(
                plan_id=plan_id,
                goal=goal,
                status=CoordinationStatus.FAILED,
                summary=f"Coordination failed: {str(e)}",
                duration_ms=(time.monotonic() - started_at) * 1000,
            )
            self._completed_results[plan_id] = result
            return result

    # ── Phase: Plan ──

    async def plan(
        self, goal: str, context: Optional[Dict[str, Any]] = None,
    ) -> CoordinationPlan:
        """Decompose a user goal into a task graph.

        Args:
            goal: The user goal.
            context: Optional additional context.

        Returns:
            A coordination plan with subtasks and task graph.
        """
        logger.debug("Planning for goal: %s", goal)

        if self._task_planner:
            plan_result = await self._task_planner.plan(
                PlanRequest(goal=goal, context=context or {}),
            )
            subtasks = plan_result.subtasks
        else:
            # Default decomposition: split by domain keywords
            subtasks = self._decompose_goal(goal)

        task_graph = TaskGraph()
        for subtask in subtasks:
            node = TaskNode(
                node_id=subtask.get("id", uuid.uuid4().hex[:8]),
                name=subtask.get("name", "task"),
                description=subtask.get("description", ""),
                required_capabilities=subtask.get("capabilities", []),
            )
            task_graph.add_node(node)

        return CoordinationPlan(
            plan_id="",
            goal=goal,
            subtasks=subtasks,
            task_graph=task_graph,
        )

    def _decompose_goal(self, goal: str) -> List[Dict[str, Any]]:
        """Decompose a goal into subtasks by domain keywords.

        Args:
            goal: The user goal.

        Returns:
            List of subtask dictionaries.
        """
        goal_lower = goal.lower()
        subtasks: List[Dict[str, Any]] = []

        domain_patterns = [
            ("market_analysis", ["market", "price", "quote", "analyze market"], ["market.analysis"]),
            ("research", ["research", "backtest", "factor", "analyze"], ["research.execute"]),
            ("risk_assessment", ["risk", "var", "exposure", "stress"], ["risk.assessment"]),
            ("strategy", ["strategy", "signal", "alpha"], ["strategy.develop"]),
            ("portfolio", ["portfolio", "allocation", "rebalance"], ["portfolio.manage"]),
            ("execution", ["execution", "order", "trade"], ["execution.manage"]),
            ("report", ["report", "summary", "document"], ["reporting.generate"]),
        ]

        for name, keywords, capabilities in domain_patterns:
            if any(kw in goal_lower for kw in keywords):
                subtasks.append({
                    "id": uuid.uuid4().hex[:8],
                    "name": name,
                    "description": f"Execute {name} for: {goal}",
                    "capabilities": capabilities,
                })

        # Always add a reporting subtask if any other subtasks exist
        if subtasks and not any(s["name"] == "report" for s in subtasks):
            subtasks.append({
                "id": uuid.uuid4().hex[:8],
                "name": "report",
                "description": f"Generate summary report for: {goal}",
                "capabilities": ["reporting.generate"],
            })

        return subtasks

    # ── Phase: Discover ──

    async def _discover_agents(
        self, plan: CoordinationPlan,
    ) -> Dict[str, List[DiscoveryResult]]:
        """Discover agents for each subtask in the plan.

        Args:
            plan: The coordination plan.

        Returns:
            Mapping of subtask ID to discovered agents.
        """
        assignments: Dict[str, List[DiscoveryResult]] = {}
        for subtask in plan.subtasks:
            query = DiscoveryQuery(
                task_description=subtask.get("description", ""),
                required_capabilities=subtask.get("capabilities", []),
            )
            results = await self._discovery.discover(query)
            assignments[subtask["id"]] = results
            plan.agent_assignments[subtask["id"]] = (
                results[0].agent.agent_id if results else ""
            )
            logger.debug("Discovered %d agents for subtask '%s'",
                         len(results), subtask["name"])
        return assignments

    # ── Phase: Route ──

    async def _route_tasks(
        self, plan: CoordinationPlan,
        assignments: Dict[str, List[DiscoveryResult]],
    ) -> List[RouteDecision]:
        """Route each subtask to its assigned agents.

        Args:
            plan: The coordination plan.
            assignments: Agent discovery results per subtask.

        Returns:
            List of route decisions.
        """
        decisions: List[RouteDecision] = []
        for subtask in plan.subtasks:
            agents = assignments.get(subtask["id"], [])
            if not agents:
                logger.warning("No agents found for subtask: %s", subtask["name"])
                continue

            request = RouteRequest(
                task_description=subtask.get("description", ""),
                required_capabilities=subtask.get("capabilities", []),
                strategy=RouteStrategy.SERIAL,
                preferred_agent_ids=[agents[0].agent.agent_id] if agents else [],
            )
            decision = await self._router.route(request)
            decisions.append(decision)

        return decisions

    # ── Phase: Execute ──

    async def _execute_tasks(
        self, decisions: List[RouteDecision],
    ) -> List[DispatchResult]:
        """Execute all routed tasks.

        Args:
            decisions: Route decisions for each task.

        Returns:
            List of dispatch results.
        """
        all_results: List[DispatchResult] = []
        for decision in decisions:
            results = await self._dispatcher.dispatch_from_decision(decision)
            all_results.extend(results)
        return all_results

    # ── Phase: Consensus ──

    async def _reach_consensus(
        self, results: List[DispatchResult], goal: str,
    ) -> Optional[ConsensusResult]:
        """Reach consensus among multiple agent results.

        Args:
            results: Dispatch results from agents.
            goal: The original user goal.

        Returns:
            Consensus result or None.
        """
        proposal = ConsensusProposal(
            proposal_id=uuid.uuid4().hex[:8],
            topic=goal,
            options=[r.output for r in results if r.output],
            metadata={"result_count": len(results)},
        )
        consensus = await self._consensus_engine.reach_consensus(proposal)
        return consensus

    # ── Phase: Finalize ──

    async def finalize(
        self,
        plan_id: str,
        results: List[DispatchResult],
        consensus: Optional[ConsensusResult] = None,
    ) -> CoordinationResult:
        """Finalize the coordination cycle and produce the result.

        Args:
            plan_id: The coordination plan ID.
            results: Dispatch results from all agents.
            consensus: Consensus result if applicable.

        Returns:
            Final coordination result.
        """
        plan = self._active_plans.get(plan_id)
        goal = plan.goal if plan else "unknown"
        duration = 0.0
        if plan:
            duration = (time.monotonic() - plan.created_at) * 1000

        success_count = sum(1 for r in results if r.is_success)
        status = CoordinationStatus.COMPLETED if success_count > 0 else CoordinationStatus.FAILED

        return CoordinationResult(
            plan_id=plan_id,
            goal=goal,
            status=status,
            results=results,
            consensus=consensus,
            duration_ms=duration,
            summary=f"Completed {success_count}/{len(results)} tasks"
                     f" for goal: {goal[:100]}",
        )

    # ── Quick Coordination ──

    async def assign(self, agent_id: str, task_description: str) -> DispatchResult:
        """Quickly assign a single task to a specific agent.

        Args:
            agent_id: Target agent ID.
            task_description: Task description.

        Returns:
            Dispatch result.
        """
        task = DispatchTask(
            task_id=uuid.uuid4().hex[:12],
            agent_id=agent_id,
            payload={"task_description": task_description},
        )
        return await self._dispatcher.dispatch(task)

    # ── Status ──

    def get_summary(self) -> Dict[str, Any]:
        """Return a summary of the coordinator state.

        Returns:
            Dict with plan counts and status.
        """
        return {
            "initialized": self._initialized,
            "active_plans": len(self._active_plans),
            "completed_results": len(self._completed_results),
        }
