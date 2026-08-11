"""Tool Router — unified routing from plan to platform tools.

Pipeline:
    Planner -> Router
        -> RouteDecision (which tool / which platform)
        -> WorkflowTool | ResearchTool | RiskTool | StrategyTool | MarketTool
        -> Tool Executor

Supports serial, parallel, and conditional routing modes.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from services.ai_agent.tooling.tool_definition import ToolDefinition
from services.ai_agent.tooling.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)


# ── Enums ──

class RouteMode(str, Enum):
    """Routing execution mode."""

    SERIAL = "serial"  # Execute one at a time
    PARALLEL = "parallel"  # Execute all concurrently
    CONDITIONAL = "conditional"  # Execute based on conditions
    FALLBACK = "fallback"  # Try primary, fall back to alternate


class RouteStrategy(str, Enum):
    """Routing strategy for tool selection."""

    DIRECT = "direct"  # Use exactly the specified tool
    BEST_MATCH = "best_match"  # Select best matching tool
    BROADCAST = "broadcast"  # Send to all matching tools
    ROUND_ROBIN = "round_robin"  # Distribute across tools


# ── RouteDecision ──

@dataclass
class RouteDecision:
    """A single routing decision for a tool call."""

    tool_name: str
    platform: str = ""  # workflow | research | risk | strategy | market | scheduler
    mode: RouteMode = RouteMode.SERIAL
    priority: int = 0
    params: Dict[str, Any] = field(default_factory=dict)
    condition: Optional[str] = None  # Conditional expression for CONDITIONAL mode
    depends_on: List[str] = field(default_factory=list)  # Tool names to wait for
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "tool_name": self.tool_name,
            "platform": self.platform,
            "mode": self.mode.value,
            "priority": self.priority,
            "params": self.params,
            "condition": self.condition,
            "depends_on": self.depends_on,
        }


# ── RoutePlan ──

@dataclass
class RoutePlan:
    """A complete routing plan with multiple decisions."""

    plan_id: str = ""
    decisions: List[RouteDecision] = field(default_factory=list)
    strategy: RouteStrategy = RouteStrategy.DIRECT
    mode: RouteMode = RouteMode.SERIAL
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def tool_count(self) -> int:
        return len(self.decisions)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "plan_id": self.plan_id,
            "decisions": [d.to_dict() for d in self.decisions],
            "strategy": self.strategy.value,
            "mode": self.mode.value,
            "tool_count": self.tool_count,
        }


# ── ToolRouter ──

class ToolRouter:
    """Unified tool router that maps agent intents to platform tool calls.

    Determines which tool(s) to invoke and how to execute them:
    serial (one-by-one), parallel (concurrent), conditional (if/else),
    or fallback (primary with backup).

    Supports:
        - Serial, parallel, conditional, and fallback routing
        - Direct, best-match, broadcast, and round-robin strategies
        - Dependency ordering
        - Priority-based ordering
        - Platform-specific routing hints

    Usage:
        router = ToolRouter(registry)
        plan = await router.route(tool_names=["backtest.run"], mode=RouteMode.SERIAL)
    """

    def __init__(self, registry: ToolRegistry) -> None:
        """Initialize the router.

        Args:
            registry: The ToolRegistry for tool resolution.
        """
        self._registry = registry
        self._initialized: bool = False
        logger.info("ToolRouter created")

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize the router."""
        self._initialized = True
        logger.info("ToolRouter initialized")

    async def shutdown(self) -> None:
        """Shutdown the router."""
        self._initialized = False
        logger.info("ToolRouter shutdown complete")

    # ── Routing ──

    async def route(
        self,
        tool_names: List[str],
        mode: RouteMode = RouteMode.SERIAL,
        strategy: RouteStrategy = RouteStrategy.DIRECT,
        params: Optional[Dict[str, Dict[str, Any]]] = None,
        dependencies: Optional[Dict[str, List[str]]] = None,
        conditions: Optional[Dict[str, str]] = None,
        priorities: Optional[Dict[str, int]] = None,
    ) -> RoutePlan:
        """Create a routing plan for the specified tools.

        Args:
            tool_names: List of tool names to invoke.
            mode: Execution mode (serial/parallel/conditional/fallback).
            strategy: Selection strategy.
            params: Per-tool parameter overrides.
            dependencies: Per-tool dependency declarations.
            conditions: Per-tool condition expressions.
            priorities: Per-tool priority values.

        Returns:
            A RoutePlan with ordered decisions.

        Raises:
            KeyError: If a tool is not found in the registry.
        """
        from uuid import uuid4

        plan_id = uuid4().hex
        decisions: List[RouteDecision] = []

        for name in tool_names:
            tool = self._registry.lookup(name)
            if tool is None:
                raise KeyError(f"Tool not found in registry: {name}")

            platform = self._infer_platform(tool)

            decision = RouteDecision(
                tool_name=name,
                platform=platform,
                mode=mode,
                priority=priorities.get(name, 0) if priorities else 0,
                params=params.get(name, {}) if params else {},
                condition=conditions.get(name) if conditions else None,
                depends_on=dependencies.get(name, []) if dependencies else [],
            )
            decisions.append(decision)

        # Sort by priority (descending) then by dependency order
        decisions.sort(key=lambda d: (-d.priority, len(d.depends_on)))

        plan = RoutePlan(
            plan_id=plan_id,
            decisions=decisions,
            strategy=strategy,
            mode=mode,
        )

        logger.info(
            f"Route plan created: {plan_id}, {len(decisions)} tools, "
            f"mode={mode.value}, strategy={strategy.value}"
        )

        return plan

    async def route_single(
        self,
        tool_name: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> RoutePlan:
        """Route a single tool call.

        Args:
            tool_name: The tool to invoke.
            params: Parameters for the tool.

        Returns:
            A RoutePlan with a single decision.
        """
        return await self.route(
            tool_names=[tool_name],
            mode=RouteMode.SERIAL,
            strategy=RouteStrategy.DIRECT,
            params={tool_name: params} if params else None,
        )

    async def route_parallel(
        self,
        tool_names: List[str],
        params: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> RoutePlan:
        """Route multiple tools in parallel.

        Args:
            tool_names: Tools to execute concurrently.
            params: Per-tool parameters.

        Returns:
            A RoutePlan with parallel decisions.
        """
        return await self.route(
            tool_names=tool_names,
            mode=RouteMode.PARALLEL,
            strategy=RouteStrategy.BROADCAST,
            params=params,
        )

    async def route_conditional(
        self,
        tool_name: str,
        condition: str,
        fallback_name: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> RoutePlan:
        """Route a conditional tool call with optional fallback.

        Args:
            tool_name: Primary tool.
            condition: Condition expression.
            fallback_name: Optional fallback tool.
            params: Parameters for the primary tool.

        Returns:
            A RoutePlan with conditional decision.
        """
        names = [tool_name]
        if fallback_name:
            names.append(fallback_name)

        params_dict: Dict[str, Dict[str, Any]] = {}
        if params:
            params_dict[tool_name] = params

        conditions: Dict[str, str] = {tool_name: condition}

        return await self.route(
            tool_names=names,
            mode=RouteMode.CONDITIONAL if fallback_name else RouteMode.CONDITIONAL,
            params=params_dict,
            conditions=conditions,
        )

    # ── Execution ──

    async def execute_plan(
        self,
        plan: RoutePlan,
        executor: Any = None,  # ToolExecutor (lazy import to avoid circular)
    ) -> List[Dict[str, Any]]:
        """Execute a routing plan.

        Args:
            plan: The RoutePlan to execute.
            executor: The ToolExecutor instance.

        Returns:
            List of execution results per tool.
        """
        results: List[Dict[str, Any]] = []

        if plan.mode == RouteMode.PARALLEL:
            # Execute all decisions concurrently
            tasks = []
            for decision in plan.decisions:
                tasks.append(self._execute_decision(decision, executor))
            parallel_results = await asyncio.gather(*tasks, return_exceptions=True)
            for i, result in enumerate(parallel_results):
                if isinstance(result, Exception):
                    results.append({
                        "tool": plan.decisions[i].tool_name,
                        "success": False,
                        "error": str(result),
                    })
                else:
                    results.append(result)
        else:
            # Serial execution
            for decision in plan.decisions:
                result = await self._execute_decision(decision, executor)
                results.append(result)

        return results

    async def _execute_decision(
        self,
        decision: RouteDecision,
        executor: Any = None,
    ) -> Dict[str, Any]:
        """Execute a single routing decision.

        Args:
            decision: The routing decision.
            executor: The ToolExecutor instance.

        Returns:
            Execution result dictionary.
        """
        if executor and hasattr(executor, "execute"):
            try:
                result = await executor.execute(
                    tool_name=decision.tool_name,
                    params=decision.params,
                )
                return {
                    "tool": decision.tool_name,
                    "success": result.success if hasattr(result, "success") else True,
                    "platform": decision.platform,
                    "data": result.data if hasattr(result, "data") else result,
                }
            except Exception as e:
                logger.exception(f"Route execution failed for {decision.tool_name}: {e}")
                return {
                    "tool": decision.tool_name,
                    "success": False,
                    "platform": decision.platform,
                    "error": str(e),
                }

        return {
            "tool": decision.tool_name,
            "success": False,
            "platform": decision.platform,
            "error": "No executor available",
        }

    # ── Private Methods ──

    def _infer_platform(self, tool: ToolDefinition) -> str:
        """Infer the platform from a tool definition.

        Args:
            tool: The tool definition.

        Returns:
            Platform name.
        """
        category_map = {
            "workflow": "workflow",
            "research": "research",
            "risk": "risk",
            "strategy": "strategy",
            "market_data": "market_data",
            "portfolio": "portfolio",
            "scheduler": "scheduler",
            "order": "oms",
        }
        return category_map.get(tool.category, "general")

    # ── Status ──

    def get_summary(self) -> Dict[str, Any]:
        """Get router status."""
        return {
            "initialized": self._initialized,
            "registry_tools": self._registry.active_count,
        }
