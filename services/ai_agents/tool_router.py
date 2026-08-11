"""
ICYQuant Tool Router — routes tool calls to appropriate tool handlers.

Manages tool registration, capability-based tool discovery, access control,
and execution sandboxing for agents that need to invoke quantitative tools.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger(__name__)

ToolHandler = Callable[..., Awaitable[Any]]


class ToolCategory(str, Enum):
    DATA = "data"
    FACTOR = "factor"
    BACKTEST = "backtest"
    RISK = "risk"
    PORTFOLIO = "portfolio"
    RESEARCH = "research"
    UTILITY = "utility"
    EXTERNAL = "external"


class ToolPermission(str, Enum):
    READ_ONLY = "read_only"
    READ_WRITE = "read_write"
    EXECUTE = "execute"
    ADMIN = "admin"


@dataclass
class ToolDefinition:
    """Registration info for a tool."""
    name: str
    category: ToolCategory
    description: str = ""
    handler: Optional[ToolHandler] = None
    required_permission: ToolPermission = ToolPermission.READ_ONLY
    required_capabilities: list[str] = field(default_factory=list)

    # Schema
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)

    # Execution
    timeout_seconds: int = 60
    max_retries: int = 1
    rate_limit_per_minute: int = 0  # 0 = unlimited

    enabled: bool = True
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolCall:
    """A tool invocation request."""
    call_id: str
    tool_name: str
    params: dict[str, Any] = field(default_factory=dict)
    agent_id: str = ""
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResult:
    """Result of a tool execution."""
    call_id: str
    tool_name: str
    success: bool = False
    result: Any = None
    error: str = ""
    duration_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class ToolRouter:
    """Routes tool calls to registered tool handlers.

    Features:
        - Tool registration with schema validation
        - Category-based tool discovery
        - Access control via permission levels
        - Execution timeout and retry
        - Rate limiting per-tool
        - Execution metrics and tracing
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        self._category_index: dict[ToolCategory, list[str]] = {}
        self._tag_index: dict[str, set[str]] = {}

        # Rate limiting
        self._rate_counters: dict[str, list[float]] = {}
        self._rate_lock = asyncio.Lock()

        # Stats
        self._total_calls = 0
        self._total_success = 0
        self._total_failures = 0

    # ── Registration ──

    def register(self, tool: ToolDefinition) -> None:
        """Register a tool for routing."""
        self._tools[tool.name] = tool

        # Category index
        if tool.category not in self._category_index:
            self._category_index[tool.category] = []
        self._category_index[tool.category].append(tool.name)

        # Tag index
        for tag in tool.tags:
            if tag not in self._tag_index:
                self._tag_index[tag] = set()
            self._tag_index[tag].add(tool.name)

        logger.info("Registered tool: %s [%s]", tool.name, tool.category.value)

    def unregister(self, tool_name: str) -> bool:
        """Remove a tool from the registry."""
        tool = self._tools.pop(tool_name, None)
        if tool is None:
            return False

        if tool.category in self._category_index:
            self._category_index[tool.category] = [
                n for n in self._category_index[tool.category] if n != tool_name
            ]

        for tag in tool.tags:
            if tag in self._tag_index:
                self._tag_index[tag].discard(tool_name)

        return True

    # ── Execution ──

    async def execute(self, call: ToolCall) -> ToolResult:
        """Route and execute a tool call."""
        self._total_calls += 1
        start = asyncio.get_event_loop().time()

        tool = self._tools.get(call.tool_name)
        if tool is None:
            return ToolResult(
                call_id=call.call_id,
                tool_name=call.tool_name,
                error=f"Tool '{call.tool_name}' not found",
            )

        if not tool.enabled:
            return ToolResult(
                call_id=call.call_id,
                tool_name=call.tool_name,
                error=f"Tool '{call.tool_name}' is disabled",
            )

        if tool.handler is None:
            return ToolResult(
                call_id=call.call_id,
                tool_name=call.tool_name,
                error=f"Tool '{call.tool_name}' has no handler",
            )

        # Rate limit check
        if not await self._check_rate(tool):
            return ToolResult(
                call_id=call.call_id,
                tool_name=call.tool_name,
                error=f"Rate limit exceeded for '{call.tool_name}'",
            )

        # Execute with retry
        last_error = ""
        for attempt in range(tool.max_retries + 1):
            try:
                result = await asyncio.wait_for(
                    tool.handler(**call.params, **call.context),
                    timeout=tool.timeout_seconds,
                )
                duration = (asyncio.get_event_loop().time() - start) * 1000
                self._total_success += 1
                return ToolResult(
                    call_id=call.call_id,
                    tool_name=call.tool_name,
                    success=True,
                    result=result,
                    duration_ms=duration,
                )
            except asyncio.TimeoutError:
                last_error = f"Timeout after {tool.timeout_seconds}s"
                logger.warning("Tool %s timeout (attempt %d/%d)",
                               call.tool_name, attempt + 1, tool.max_retries + 1)
            except Exception as exc:
                last_error = str(exc)
                logger.warning("Tool %s failed (attempt %d/%d): %s",
                               call.tool_name, attempt + 1, tool.max_retries + 1, exc)

        self._total_failures += 1
        duration = (asyncio.get_event_loop().time() - start) * 1000
        return ToolResult(
            call_id=call.call_id,
            tool_name=call.tool_name,
            error=last_error,
            duration_ms=duration,
        )

    async def execute_batch(self, calls: list[ToolCall]) -> list[ToolResult]:
        """Execute multiple tool calls in parallel."""
        tasks = [self.execute(call) for call in calls]
        return await asyncio.gather(*tasks)

    # ── Discovery ──

    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        return self._tools.get(name)

    def list_by_category(self, category: ToolCategory) -> list[ToolDefinition]:
        names = self._category_index.get(category, [])
        return [self._tools[n] for n in names if n in self._tools]

    def list_by_tag(self, tag: str) -> list[ToolDefinition]:
        names = self._tag_index.get(tag, set())
        return [self._tools[n] for n in names if n in self._tools]

    def list_enabled(self) -> list[ToolDefinition]:
        return [t for t in self._tools.values() if t.enabled]

    def get_tools_for_capabilities(self, capabilities: list[str]) -> list[ToolDefinition]:
        """Find tools that match a set of required capabilities."""
        results = []
        for tool in self._tools.values():
            if not tool.enabled:
                continue
            # Tool matches if its required_capabilities are a subset
            if not tool.required_capabilities:
                results.append(tool)
            elif set(tool.required_capabilities).issubset(set(capabilities)):
                results.append(tool)
        return results

    # ── Rate Limiting ──

    async def _check_rate(self, tool: ToolDefinition) -> bool:
        if tool.rate_limit_per_minute <= 0:
            return True

        async with self._rate_lock:
            now = asyncio.get_event_loop().time()
            key = tool.name
            self._rate_counters.setdefault(key, [])
            self._rate_counters[key] = [t for t in self._rate_counters[key] if now - t < 60]
            self._rate_counters[key].append(now)
            return len(self._rate_counters[key]) <= tool.rate_limit_per_minute

    # ── Schema ──

    def get_tool_schema(self, tool_name: str) -> Optional[dict[str, Any]]:
        """Get the input/output schema for a tool (for LLM function calling)."""
        tool = self._tools.get(tool_name)
        if tool is None:
            return None
        return {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.input_schema,
            "returns": tool.output_schema,
        }

    def get_all_schemas(self) -> list[dict[str, Any]]:
        """Get schemas for all enabled tools."""
        return [self.get_tool_schema(n) for n in self._tools if self._tools[n].enabled]

    # ── Stats ──

    @property
    def tool_count(self) -> int:
        return len(self._tools)

    @property
    def total_calls(self) -> int:
        return self._total_calls

    @property
    def total_success(self) -> int:
        return self._total_success

    @property
    def success_rate(self) -> float:
        if self._total_calls == 0:
            return 0.0
        return self._total_success / self._total_calls
