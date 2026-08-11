"""Tool Runtime — execution environment and resource management for tool calls.

Pipeline:
    Tool Execution Request
        -> ToolRuntime (concurrency, timeout, resource limits)
        -> Tool Handler
        -> ToolResult
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── RuntimeConfig ──

@dataclass
class RuntimeConfig:
    """Configuration for the tool runtime environment."""

    # ── Concurrency ──
    max_concurrent_executions: int = 50
    max_concurrent_per_tool: int = 10

    # ── Timeouts ──
    default_timeout_seconds: float = 30.0
    max_timeout_seconds: float = 300.0

    # ── Rate Limiting ──
    default_rate_limit_per_second: Optional[float] = None
    enable_rate_limiting: bool = True

    # ── Queue ──
    max_queue_size: int = 1000
    queue_timeout_seconds: float = 60.0

    # ── Monitoring ──
    collect_metrics: bool = True
    log_execution_details: bool = True


# ── ExecutionSlot ──

@dataclass
class ExecutionSlot:
    """Tracks an active execution slot."""

    execution_id: str
    tool_name: str
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "running"  # running | completed | failed | cancelled


# ── ToolRuntime ──

class ToolRuntime:
    """Manages the execution environment for tool calls.

    Controls concurrency, timeouts, rate limiting, and resource
    allocation for all tool invocations. Ensures safe and predictable
    execution behavior.

    Supports:
        - Global and per-tool concurrency limits
        - Configurable timeouts
        - Rate limiting
        - Execution queue management
        - Slot tracking
        - Graceful cancellation

    Usage:
        runtime = ToolRuntime(RuntimeConfig(max_concurrent_executions=50))
        await runtime.initialize()
        async with runtime.acquire_slot("backtest.run") as slot:
            result = await execute_tool(...)
    """

    def __init__(self, config: Optional[RuntimeConfig] = None) -> None:
        """Initialize the runtime.

        Args:
            config: Runtime configuration.
        """
        self._config = config or RuntimeConfig()
        self._initialized: bool = False

        # ── Concurrency Control ──
        self._global_semaphore = asyncio.Semaphore(self._config.max_concurrent_executions)
        self._per_tool_semaphores: Dict[str, asyncio.Semaphore] = {}

        # ── Rate Limiting ──
        self._rate_limiters: Dict[str, float] = {}  # tool_name -> last_call_timestamp
        self._rate_limit_intervals: Dict[str, float] = {}  # tool_name -> min_interval_seconds

        # ── Execution Tracking ──
        self._active_slots: Dict[str, ExecutionSlot] = {}
        self._execution_count: int = 0
        self._total_execution_count: int = 0

        # ── Queue ──
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=self._config.max_queue_size)

        logger.info(
            f"ToolRuntime created (max_concurrent={self._config.max_concurrent_executions}, "
            f"per_tool={self._config.max_concurrent_per_tool})"
        )

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize the runtime."""
        self._initialized = True
        logger.info("ToolRuntime initialized")

    async def shutdown(self) -> None:
        """Shutdown the runtime, canceling active executions."""
        self._initialized = False

        # Cancel all active slots
        for slot in list(self._active_slots.values()):
            slot.status = "cancelled"
        self._active_slots.clear()
        self._per_tool_semaphores.clear()

        logger.info("ToolRuntime shutdown complete")

    # ── Acquisition ──

    async def acquire_slot(self, tool_name: str) -> ExecutionSlot:
        """Acquire an execution slot for a tool call.

        Blocks until a slot is available, respecting global and per-tool
        concurrency limits.

        Args:
            tool_name: The tool requesting execution.

        Returns:
            An ExecutionSlot for the tool call.

        Raises:
            asyncio.TimeoutError: If queue timeout is exceeded.
        """
        from uuid import uuid4

        execution_id = uuid4().hex

        # Apply rate limiting
        await self._check_rate_limit(tool_name)

        # Acquire per-tool semaphore
        if tool_name not in self._per_tool_semaphores:
            self._per_tool_semaphores[tool_name] = asyncio.Semaphore(
                self._config.max_concurrent_per_tool
            )
        per_tool_sem = self._per_tool_semaphores[tool_name]

        # Acquire both semaphores (global first, then per-tool)
        try:
            await asyncio.wait_for(
                self._global_semaphore.acquire(),
                timeout=self._config.queue_timeout_seconds,
            )
            await asyncio.wait_for(
                per_tool_sem.acquire(),
                timeout=self._config.queue_timeout_seconds,
            )
        except asyncio.TimeoutError:
            # Release any acquired semaphore
            if self._global_semaphore.locked():
                self._global_semaphore.release()
            raise

        slot = ExecutionSlot(execution_id=execution_id, tool_name=tool_name)
        self._active_slots[execution_id] = slot
        self._execution_count += 1
        self._total_execution_count += 1

        logger.debug(f"Slot acquired: {execution_id} for {tool_name}")
        return slot

    def release_slot(self, slot: ExecutionSlot, success: bool = True) -> None:
        """Release an execution slot after tool completion.

        Args:
            slot: The execution slot to release.
            success: Whether the execution was successful.
        """
        slot.status = "completed" if success else "failed"

        # Release per-tool semaphore
        if slot.tool_name in self._per_tool_semaphores:
            self._per_tool_semaphores[slot.tool_name].release()

        # Release global semaphore
        self._global_semaphore.release()

        self._execution_count -= 1

        logger.debug(f"Slot released: {slot.execution_id} for {slot.tool_name}")

    # ── Timeout Helpers ──

    async def execute_with_timeout(
        self,
        tool_name: str,
        timeout_seconds: Optional[float],
        coro: Any,
    ) -> Any:
        """Execute a coroutine with timeout enforcement.

        Args:
            tool_name: The tool name (for logging).
            timeout_seconds: The timeout in seconds.
            coro: The coroutine to execute.

        Returns:
            The coroutine result.

        Raises:
            asyncio.TimeoutError: If execution exceeds timeout.
        """
        timeout = min(
            timeout_seconds or self._config.default_timeout_seconds,
            self._config.max_timeout_seconds,
        )
        try:
            result = await asyncio.wait_for(coro, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            logger.warning(f"Tool execution timed out: {tool_name} ({timeout}s)")
            raise

    # ── Rate Limiting ──

    async def _check_rate_limit(self, tool_name: str) -> None:
        """Check and enforce rate limiting for a tool.

        Args:
            tool_name: The tool to check.
        """
        if not self._config.enable_rate_limiting:
            return

        interval = self._rate_limit_intervals.get(tool_name)
        if interval is None:
            return

        last_call = self._rate_limiters.get(tool_name, 0.0)
        now = time.monotonic()
        elapsed = now - last_call

        if elapsed < interval:
            wait_time = interval - elapsed
            logger.debug(f"Rate limiting {tool_name}: waiting {wait_time:.2f}s")
            await asyncio.sleep(wait_time)

        self._rate_limiters[tool_name] = time.monotonic()

    def set_rate_limit(self, tool_name: str, per_second: float) -> None:
        """Set a rate limit for a specific tool.

        Args:
            tool_name: The tool name.
            per_second: Maximum calls per second.
        """
        if per_second <= 0:
            self._rate_limit_intervals.pop(tool_name, None)
        else:
            self._rate_limit_intervals[tool_name] = 1.0 / per_second

    # ── Status ──

    @property
    def active_count(self) -> int:
        """Number of currently active executions."""
        return self._execution_count

    @property
    def is_at_capacity(self) -> bool:
        """Whether the runtime is at max capacity."""
        return self._execution_count >= self._config.max_concurrent_executions

    def get_summary(self) -> Dict[str, Any]:
        """Get runtime status summary."""
        return {
            "active_executions": self._execution_count,
            "total_executions": self._total_execution_count,
            "max_concurrent": self._config.max_concurrent_executions,
            "per_tool_limit": self._config.max_concurrent_per_tool,
            "queue_size": self._queue.qsize(),
            "rate_limited_tools": list(self._rate_limit_intervals.keys()),
            "active_slots": [
                {"execution_id": eid, "tool": s.tool_name, "status": s.status}
                for eid, s in self._active_slots.items()
            ],
        }
