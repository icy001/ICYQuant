"""Agent Router — unified routing of tasks to agents based on capability and availability.

Pipeline:
    RouteRequest (task + requirements)
        -> AgentDiscovery (find candidate agents)
        -> AgentRouter.evaluate() (score candidates)
        -> RouteDecision (selected agent + routing strategy)
        -> AgentDispatcher (dispatch task)

Supports serial, parallel, conditional, and fallback routing strategies.
"""

from __future__ import annotations

import logging
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

logger = logging.getLogger(__name__)


class RouteStrategy(str, Enum):
    """Routing strategy for task-to-agent assignment."""
    SERIAL = "serial"           # Route to one agent at a time
    PARALLEL = "parallel"       # Route to multiple agents concurrently
    CONDITIONAL = "conditional" # Route based on conditions
    FALLBACK = "fallback"       # Route with fallback agents
    BROADCAST = "broadcast"     # Route to all capable agents


@dataclass
class RouteRequest:
    """A request to route a task to appropriate agents.

    Attributes:
        task_description: Description of the task to route.
        required_capabilities: Required capability tags.
        strategy: Preferred routing strategy.
        preferred_agent_ids: Specific agent IDs to prefer.
        min_agents: Minimum number of agents to route to.
        max_agents: Maximum number of agents to route to.
        context: Additional routing context.
    """

    task_description: str = ""
    required_capabilities: List[str] = field(default_factory=list)
    strategy: RouteStrategy = RouteStrategy.SERIAL
    preferred_agent_ids: List[str] = field(default_factory=list)
    min_agents: int = 1
    max_agents: int = 3
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RouteDecision:
    """Result of routing a task to agents.

    Attributes:
        request: The original route request.
        selected_agents: Ordered list of selected agents with scores.
        strategy_used: The routing strategy that was applied.
        reason: Human-readable explanation of the routing decision.
    """

    request: RouteRequest = field(default_factory=RouteRequest)
    selected_agents: List[DiscoveryResult] = field(default_factory=list)
    strategy_used: RouteStrategy = RouteStrategy.SERIAL
    reason: str = ""

    @property
    def has_results(self) -> bool:
        """Return whether any agents were selected."""
        return len(self.selected_agents) > 0

    def to_dict(self) -> Dict[str, Any]:
        """Return decision as a dictionary."""
        return {
            "strategy": self.strategy_used.value,
            "reason": self.reason,
            "agents": [r.to_dict() for r in self.selected_agents],
        }


class AgentRouter:
    """Unified router for assigning tasks to the most appropriate agents.

    Evaluates candidate agents discovered by AgentDiscovery and makes
    routing decisions based on agent availability, capability match,
    priority, and routing strategy.

    Supports:
        - Serial routing (best single agent)
        - Parallel routing (multiple agents concurrently)
        - Conditional routing (rule-based agent selection)
        - Fallback routing (primary + backup agents)
        - Broadcast routing (all capable agents)
        - Priority-weighted selection

    Usage:
        router = AgentRouter(registry, discovery)
        await router.initialize()
        request = RouteRequest(task_description="Run backtest", ...)
        decision = await router.route(request)
    """

    def __init__(self, registry: AgentRegistry, discovery: AgentDiscovery) -> None:
        """Initialize the agent router.

        Args:
            registry: Agent registry for agent data.
            discovery: Agent discovery for finding candidates.
        """
        self._registry: AgentRegistry = registry
        self._discovery: AgentDiscovery = discovery
        self._initialized: bool = False
        logger.info("AgentRouter created")

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize the router."""
        if self._initialized:
            logger.warning("AgentRouter already initialized")
            return
        self._initialized = True
        logger.info("AgentRouter initialized")

    async def shutdown(self) -> None:
        """Shut down the router."""
        if not self._initialized:
            return
        self._initialized = False
        logger.info("AgentRouter shutdown complete")

    # ── Routing ──

    async def route(self, request: RouteRequest) -> RouteDecision:
        """Route a task to the best agent(s).

        Args:
            request: Route request with task and requirements.

        Returns:
            RouteDecision with selected agents and strategy.
        """
        if not self._initialized:
            raise RuntimeError("AgentRouter not initialized")

        # Discover candidate agents
        query = DiscoveryQuery(
            task_description=request.task_description,
            required_capabilities=request.required_capabilities,
            max_results=request.max_agents * 2,  # Get more for filtering
        )
        candidates = await self._discovery.discover(query)

        if not candidates:
            logger.warning("No agents found for task: %s", request.task_description)
            return RouteDecision(
                request=request,
                strategy_used=request.strategy,
                reason="No matching agents found",
            )

        # Apply routing strategy
        strategy = request.strategy
        if strategy == RouteStrategy.SERIAL:
            selected = self._route_serial(candidates, request)
        elif strategy == RouteStrategy.PARALLEL:
            selected = self._route_parallel(candidates, request)
        elif strategy == RouteStrategy.CONDITIONAL:
            selected = self._route_conditional(candidates, request)
        elif strategy == RouteStrategy.FALLBACK:
            selected = self._route_fallback(candidates, request)
        elif strategy == RouteStrategy.BROADCAST:
            selected = self._route_broadcast(candidates, request)
        else:
            selected = self._route_serial(candidates, request)

        return RouteDecision(
            request=request,
            selected_agents=selected,
            strategy_used=strategy,
            reason=f"Routed to {len(selected)} agent(s) via {strategy.value} strategy",
        )

    # ── Strategy Implementations ──

    def _route_serial(
        self, candidates: List[DiscoveryResult], request: RouteRequest,
    ) -> List[DiscoveryResult]:
        """Select the single best agent.

        Args:
            candidates: Discovered candidate agents.
            request: The route request.

        Returns:
            List with the single best agent.
        """
        # Boost preferred agents
        for candidate in candidates:
            if candidate.agent.agent_id in request.preferred_agent_ids:
                candidate.score += 0.3

        # Filter to idle/registered agents only
        available = [
            c for c in candidates
            if c.agent.status in (AgentStatus.IDLE, AgentStatus.REGISTERED)
        ]
        if available:
            available.sort(key=lambda c: c.score, reverse=True)
            return [available[0]]
        # Fall back to busy agents if none idle
        candidates.sort(key=lambda c: c.score, reverse=True)
        return candidates[:1]

    def _route_parallel(
        self, candidates: List[DiscoveryResult], request: RouteRequest,
    ) -> List[DiscoveryResult]:
        """Select multiple agents for parallel execution.

        Args:
            candidates: Discovered candidate agents.
            request: The route request.

        Returns:
            List of selected agents (up to max_agents).
        """
        available = [
            c for c in candidates
            if c.agent.status in (AgentStatus.IDLE, AgentStatus.REGISTERED)
        ]
        if not available:
            available = candidates

        available.sort(key=lambda c: c.score, reverse=True)
        count = max(request.min_agents, min(request.max_agents, len(available)))
        return available[:count]

    def _route_conditional(
        self, candidates: List[DiscoveryResult], request: RouteRequest,
    ) -> List[DiscoveryResult]:
        """Select agents based on conditions in the request context.

        Args:
            candidates: Discovered candidate agents.
            request: The route request.

        Returns:
            List of conditionally selected agents.
        """
        conditions = request.context.get("conditions", {})
        required_role = conditions.get("role")
        required_domain = conditions.get("domain")

        filtered = candidates
        if required_role:
            filtered = [
                c for c in filtered
                if c.agent.role.value == required_role
            ]
        if required_domain:
            filtered = [
                c for c in filtered
                if any(required_domain in cap for cap in c.agent.capabilities)
            ]

        if not filtered:
            filtered = candidates  # Fall back to all

        filtered.sort(key=lambda c: c.score, reverse=True)
        return filtered[:request.max_agents]

    def _route_fallback(
        self, candidates: List[DiscoveryResult], request: RouteRequest,
    ) -> List[DiscoveryResult]:
        """Select primary agent with fallback options.

        Args:
            candidates: Discovered candidate agents.
            request: The route request.

        Returns:
            List with primary agent first, then fallbacks.
        """
        candidates.sort(key=lambda c: c.score, reverse=True)
        count = min(request.max_agents, len(candidates))
        selected = candidates[:count]
        # Mark first as primary, rest as fallback
        if selected:
            selected[0].score = min(selected[0].score, 1.0)
            for i in range(1, len(selected)):
                selected[i].match_type = f"{selected[i].match_type}.fallback"
        return selected

    def _route_broadcast(
        self, candidates: List[DiscoveryResult], request: RouteRequest,
    ) -> List[DiscoveryResult]:
        """Route to all capable agents.

        Args:
            candidates: Discovered candidate agents.
            request: The route request.

        Returns:
            List of all available candidates.
        """
        candidates.sort(key=lambda c: c.score, reverse=True)
        return candidates[:request.max_agents] if request.max_agents > 0 else candidates

    # ── Status ──

    def get_summary(self) -> Dict[str, Any]:
        """Return a summary of the router state.

        Returns:
            Dict with initialization status.
        """
        return {
            "initialized": self._initialized,
        }
