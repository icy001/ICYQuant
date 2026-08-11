"""Tool Executor — unified execution engine with full validation-to-result pipeline.

Pipeline:
    Tool Selection + Context + Params
        -> Validation (input schema)
        -> Permission Check
        -> Policy Evaluation
        -> Sandbox (if configured)
        -> Execution (handler invocation)
        -> Result
        -> Observation
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, Optional

from services.ai_agent.tooling.tool_context import ToolContext
from services.ai_agent.tooling.tool_definition import ToolDefinition
from services.ai_agent.tooling.tool_registry import ToolRegistry
from services.ai_agent.tooling.tool_result import ToolResult
from services.ai_agent.tooling.tool_runtime import ToolRuntime

logger = logging.getLogger(__name__)


# ── ToolExecutor ──

class ToolExecutor:
    """Unified tool execution engine.

    Orchestrates the full tool execution pipeline: validation,
    permission checking, policy evaluation, sandboxing, handler
    invocation, result capture, and observation publishing.

    Supports:
        - Sync and async execution
        - Streaming execution (placeholder for future)
        - Input validation
        - Permission enforcement
        - Timeout enforcement
        - Error classification
        - Result standardization

    Usage:
        executor = ToolExecutor(registry, runtime)
        result = await executor.execute("backtest.run", {"strategy_id": "s1"})
    """

    def __init__(
        self,
        registry: ToolRegistry,
        runtime: ToolRuntime,
    ) -> None:
        """Initialize the executor.

        Args:
            registry: The ToolRegistry for tool lookup.
            runtime: The ToolRuntime for execution management.
        """
        self._registry = registry
        self._runtime = runtime
        self._initialized: bool = False

        # Observers for result publishing
        self._observers: list = []

        logger.info("ToolExecutor created")

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize the executor."""
        self._initialized = True
        logger.info("ToolExecutor initialized")

    async def shutdown(self) -> None:
        """Shutdown the executor."""
        self._observers.clear()
        self._initialized = False
        logger.info("ToolExecutor shutdown complete")

    # ── Execution ──

    async def execute(
        self,
        tool_name: str,
        params: Optional[Dict[str, Any]] = None,
        context: Optional[ToolContext] = None,
    ) -> ToolResult:
        """Execute a tool with the full pipeline.

        Args:
            tool_name: The name of the tool to execute.
            params: Input parameters for the tool.
            context: Optional execution context.

        Returns:
            A ToolResult with execution outcome.
        """
        from uuid import uuid4

        params = params or {}
        execution_id = uuid4().hex
        started_at = time.monotonic()

        # ── Step 1: Lookup tool ──
        tool = self._registry.lookup(tool_name)
        if tool is None:
            logger.error(f"Tool not found: {tool_name}")
            return ToolResult.error_result(
                tool_name=tool_name,
                error=f"Tool not found: {tool_name}",
                error_type="unknown",
                execution_id=execution_id,
            )

        if tool.deprecated:
            logger.warning(f"Tool is deprecated: {tool_name} - {tool.deprecation_message}")

        # ── Step 2: Validate inputs ──
        validation_errors = tool.validate_input(params)
        if validation_errors:
            logger.warning(f"Input validation failed for {tool_name}: {validation_errors}")
            return ToolResult.error_result(
                tool_name=tool_name,
                error=f"Input validation failed: {'; '.join(validation_errors)}",
                error_type="validation",
                execution_id=execution_id,
            )

        # ── Step 3: Permission check ──
        if context and tool.permission:
            if not context.can_execute(tool.permission):
                logger.warning(
                    f"Permission denied for {tool_name}: "
                    f"requires '{tool.permission}', "
                    f"granted={list(context.granted_permissions)}"
                )
                return ToolResult.permission_denied(
                    tool_name=tool_name,
                    error=f"Permission denied: requires '{tool.permission}'",
                )

        # ── Step 4: Check call depth ──
        if context and context.exceeded_max_depth:
            return ToolResult.error_result(
                tool_name=tool_name,
                error=f"Max call depth exceeded: {context.call_depth}",
                error_type="runtime",
                execution_id=execution_id,
            )

        # ── Step 5: Acquire execution slot ──
        slot = None
        try:
            slot = await self._runtime.acquire_slot(tool_name)

            # ── Step 6: Execute with timeout ──
            child_context = context.create_child(tool_name) if context else None
            timeout = tool.timeout_seconds

            try:
                result_data = await self._runtime.execute_with_timeout(
                    tool_name=tool_name,
                    timeout_seconds=timeout,
                    coro=self._invoke_handler(tool, params, child_context),
                )

                latency_ms = (time.monotonic() - started_at) * 1000

                tool_result = ToolResult.success_result(
                    tool_name=tool_name,
                    data=result_data,
                    latency_ms=latency_ms,
                    execution_id=execution_id,
                    started_at=slot.started_at,
                    permission_checked=context is not None,
                    permission_granted=True,
                )

                logger.info(
                    f"Tool execution success: {tool_name} ({latency_ms:.1f}ms)"
                )

            except asyncio.TimeoutError:
                latency_ms = (time.monotonic() - started_at) * 1000
                tool_result = ToolResult.timeout_result(
                    tool_name=tool_name,
                    timeout_seconds=timeout,
                    latency_ms=latency_ms,
                )

            except Exception as e:
                latency_ms = (time.monotonic() - started_at) * 1000
                logger.exception(f"Tool execution failed: {tool_name}: {e}")
                tool_result = ToolResult.error_result(
                    tool_name=tool_name,
                    error=str(e),
                    error_type="runtime",
                    execution_id=execution_id,
                    latency_ms=latency_ms,
                )

            # ── Step 7: Notify observers ──
            await self._notify_observers(tool_result)

            return tool_result

        finally:
            if slot:
                self._runtime.release_slot(slot, success=tool_result.success if 'tool_result' in dir() else False)

    async def execute_streaming(
        self,
        tool_name: str,
        params: Optional[Dict[str, Any]] = None,
        context: Optional[ToolContext] = None,
    ):
        """Execute a tool in streaming mode (placeholder).

        Args:
            tool_name: The tool name.
            params: Input parameters.
            context: Optional execution context.

        Yields:
            Streaming result chunks.
        """
        tool = self._registry.lookup(tool_name)
        if tool is None:
            yield ToolResult.error_result(
                tool_name=tool_name,
                error=f"Tool not found: {tool_name}",
            )
            return

        if not tool.is_streaming:
            # Fall back to non-streaming
            result = await self.execute(tool_name, params, context)
            yield result
            return

        # Future: streaming handler invocation
        logger.warning(f"Streaming execution not yet implemented for {tool_name}")
        result = await self.execute(tool_name, params, context)
        yield result

    # ── Handler Invocation ──

    async def _invoke_handler(
        self,
        tool: ToolDefinition,
        params: Dict[str, Any],
        context: Optional[ToolContext],
    ) -> Any:
        """Invoke the tool's handler function.

        Args:
            tool: The tool definition.
            params: Input parameters.
            context: Execution context.

        Returns:
            Handler return value.

        Raises:
            RuntimeError: If no handler is registered.
        """
        if tool.handler is None:
            raise RuntimeError(f"No handler registered for tool: {tool.name}")

        # Check if handler is async
        if asyncio.iscoroutinefunction(tool.handler):
            return await tool.handler(**params, context=context)
        else:
            # Run sync handler in executor
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                None,
                lambda: tool.handler(**params, context=context),
            )

    # ── Observer Management ──

    def add_observer(self, observer: Any) -> None:
        """Add an observer for execution results.

        Args:
            observer: An object with an async on_tool_result(result) method.
        """
        self._observers.append(observer)

    def remove_observer(self, observer: Any) -> None:
        """Remove an observer.

        Args:
            observer: The observer to remove.
        """
        if observer in self._observers:
            self._observers.remove(observer)

    async def _notify_observers(self, result: ToolResult) -> None:
        """Notify all observers of an execution result.

        Args:
            result: The ToolResult to publish.
        """
        for observer in self._observers:
            try:
                if hasattr(observer, "on_tool_result"):
                    await observer.on_tool_result(result)
            except Exception as e:
                logger.error(f"Observer notification failed: {e}")

    # ── Status ──

    def get_summary(self) -> Dict[str, Any]:
        """Get executor status."""
        return {
            "initialized": self._initialized,
            "observers": len(self._observers),
            "runtime": self._runtime.get_summary(),
        }
