"""Tool Manager — lifecycle coordinator for the entire tool calling subsystem.

Pipeline:
    ToolManager
        -> initialize() : bootstrap all subsystems
        -> execute()   : route through full pipeline
        -> shutdown()  : graceful teardown

The ToolManager is the single entry point for tool-related operations.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from services.ai_agent.tooling.tool_catalog import ToolCatalog
from services.ai_agent.tooling.tool_context import ToolContext
from services.ai_agent.tooling.tool_discovery import ToolDiscovery
from services.ai_agent.tooling.tool_executor import ToolExecutor
from services.ai_agent.tooling.tool_registry import ToolRegistry
from services.ai_agent.tooling.tool_result import ToolResult
from services.ai_agent.tooling.tool_router import RouteMode, RoutePlan, RouteStrategy, ToolRouter
from services.ai_agent.tooling.tool_runtime import RuntimeConfig, ToolRuntime
from services.ai_agent.tooling.tool_selector import ToolSelector

logger = logging.getLogger(__name__)


# ── ToolManager ──

class ToolManager:
    """Central lifecycle coordinator for the tool calling subsystem.

    Owns all tooling components and provides a unified API for tool
    registration, discovery, selection, routing, and execution.

    Supports:
        - Subsystem lifecycle (init/shutdown)
        - Tool registration
        - Tool discovery and selection
        - Single and batch tool execution
        - Route plan execution
        - Status reporting

    Usage:
        manager = ToolManager()
        await manager.initialize()
        manager.register_tool(my_tool_definition)
        result = await manager.execute("backtest.run", {"strategy_id": "s1"})
        await manager.shutdown()
    """

    def __init__(
        self,
        runtime_config: Optional[RuntimeConfig] = None,
    ) -> None:
        """Initialize the tool manager.

        Args:
            runtime_config: Optional runtime configuration.
        """
        # ── Subsystems ──
        self.registry = ToolRegistry()
        self.catalog = ToolCatalog()
        self.runtime = ToolRuntime(config=runtime_config)
        self.executor = ToolExecutor(registry=self.registry, runtime=self.runtime)
        self.discovery = ToolDiscovery(catalog=self.catalog)
        self.selector = ToolSelector(registry=self.registry)
        self.router = ToolRouter(registry=self.registry)

        self._initialized: bool = False
        logger.info("ToolManager created")

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize all subsystems in order."""
        logger.info("ToolManager initializing...")

        await self.registry.initialize()
        await self.catalog.initialize()
        await self.runtime.initialize()
        await self.executor.initialize()
        await self.discovery.initialize()
        await self.selector.initialize()
        await self.router.initialize()

        # Index registry into catalog
        self.catalog.index_tools(self.registry.list_all())

        self._initialized = True
        logger.info(
            f"ToolManager initialized ({self.registry.active_count} tools, "
            f"{self.catalog.entry_count} catalog entries)"
        )

    async def shutdown(self) -> None:
        """Shutdown all subsystems in reverse order."""
        logger.info("ToolManager shutting down...")

        await self.router.shutdown()
        await self.selector.shutdown()
        await self.discovery.shutdown()
        await self.executor.shutdown()
        await self.runtime.shutdown()
        await self.catalog.shutdown()
        await self.registry.shutdown()

        self._initialized = False
        logger.info("ToolManager shutdown complete")

    # ── Tool Registration ──

    def register_tool(self, tool: Any) -> None:
        """Register a tool definition.

        Args:
            tool: A ToolDefinition to register.
        """
        from services.ai_agent.tooling.tool_definition import ToolDefinition

        if isinstance(tool, ToolDefinition):
            self.registry.register(tool)
            self.catalog.index_tool(tool)
            logger.info(f"Tool registered via manager: {tool.name}")
        else:
            raise TypeError(f"Expected ToolDefinition, got {type(tool).__name__}")

    def register_tools(self, tools: List[Any]) -> None:
        """Register multiple tool definitions.

        Args:
            tools: List of ToolDefinition objects.
        """
        for tool in tools:
            self.register_tool(tool)

    # ── Execution ──

    async def execute(
        self,
        tool_name: str,
        params: Optional[Dict[str, Any]] = None,
        context: Optional[ToolContext] = None,
    ) -> ToolResult:
        """Execute a single tool.

        Args:
            tool_name: The tool to execute.
            params: Input parameters.
            context: Optional execution context.

        Returns:
            A ToolResult with execution outcome.
        """
        if not self._initialized:
            raise RuntimeError("ToolManager not initialized")

        logger.info(f"ToolManager executing: {tool_name}")
        return await self.executor.execute(tool_name, params, context)

    async def execute_plan(
        self,
        plan: RoutePlan,
        context: Optional[ToolContext] = None,
    ) -> List[Dict[str, Any]]:
        """Execute a routing plan.

        Args:
            plan: The RoutePlan to execute.
            context: Optional execution context.

        Returns:
            List of execution results per tool.
        """
        if not self._initialized:
            raise RuntimeError("ToolManager not initialized")

        return await self.router.execute_plan(plan, executor=self.executor)

    async def discover_and_execute(
        self,
        intent: str,
        params: Optional[Dict[str, Any]] = None,
        context: Optional[ToolContext] = None,
        limit: int = 5,
    ) -> Optional[ToolResult]:
        """Discover tools matching intent and execute the best match.

        Full pipeline: Discovery -> Selection -> Execution.

        Args:
            intent: Natural language task description.
            params: Input parameters.
            context: Optional execution context.
            limit: Maximum discovery results.

        Returns:
            A ToolResult, or None if no suitable tool found.
        """
        # Discover
        discovery_result = await self.discovery.discover(intent, limit=limit)
        if discovery_result.is_empty:
            logger.warning(f"No tools found for intent: {intent}")
            return None

        # Select best
        granted = context.granted_permissions if context else None
        best = await self.selector.select_best(
            discovery_result.entries,
            intent=intent,
            granted_permissions=granted,
        )
        if best is None:
            logger.warning(f"No suitable tool selected for intent: {intent}")
            return None

        # Execute
        return await self.execute(best.tool_name, params, context)

    # ── Batch Execution ──

    async def execute_batch(
        self,
        tool_names: List[str],
        params_list: Optional[List[Dict[str, Any]]] = None,
        context: Optional[ToolContext] = None,
        mode: RouteMode = RouteMode.PARALLEL,
    ) -> List[Dict[str, Any]]:
        """Execute multiple tools in batch.

        Args:
            tool_names: List of tool names.
            params_list: Per-tool parameter dictionaries.
            context: Optional execution context.
            mode: Execution mode (serial or parallel).

        Returns:
            List of execution results.
        """
        if params_list is None:
            params_list = [{} for _ in tool_names]

        params_map: Dict[str, Dict[str, Any]] = {}
        for name, p in zip(tool_names, params_list):
            params_map[name] = p

        plan = await self.router.route(
            tool_names=tool_names,
            mode=mode,
            strategy=RouteStrategy.BROADCAST,
            params=params_map,
        )

        return await self.router.execute_plan(plan, executor=self.executor)

    # ── Status ──

    def get_summary(self) -> Dict[str, Any]:
        """Get comprehensive status of the tooling subsystem."""
        return {
            "initialized": self._initialized,
            "registry": {
                "total_tools": self.registry.count,
                "active_tools": self.registry.active_count,
                "categories": self.registry.categories,
            },
            "catalog": self.catalog.get_summary(),
            "runtime": self.runtime.get_summary(),
            "executor": self.executor.get_summary(),
        }
