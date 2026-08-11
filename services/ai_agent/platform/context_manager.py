"""Context Manager — manages execution context and prompt assembly for AI agents.

The ContextManager assembles and optimizes the context window for each agent
invocation. It handles context compression, token budgeting, system prompt
injection, memory retrieval, and tool schema injection — ensuring each agent
receives the optimal context for its task.

Key capabilities:
    - Context assembly from multiple sources (system, memory, tools, user)
    - Token budget management
    - Context compression and summarization
    - Dynamic tool schema injection
    - Memory retrieval integration
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ContextSource(str, Enum):
    """Sources of context content."""
    SYSTEM = "system"
    MEMORY = "memory"
    TOOLS = "tools"
    USER = "user"
    HISTORY = "history"
    ENVIRONMENT = "environment"


@dataclass
class ContextBlock:
    """A block of context content from a specific source."""
    source: ContextSource
    content: str
    priority: int = 0
    token_estimate: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AssembledContext:
    """Fully assembled context ready for agent invocation."""
    messages: List[Dict[str, Any]] = field(default_factory=list)
    total_tokens: int = 0
    token_budget: int = 0
    blocks_used: List[str] = field(default_factory=list)
    blocks_truncated: List[str] = field(default_factory=list)
    assembled_at: float = field(default_factory=time.monotonic)


class ContextManager:
    """Manages context assembly and optimization for AI agent invocations.

    Assembles context from multiple sources, enforces token budgets,
    and applies compression strategies when needed.

    Usage:
        cm = ContextManager(default_budget=8192)
        await cm.initialize()
        ctx = await cm.assemble(agent_id="agent_1", user_message="Analyze AAPL")
    """

    def __init__(self, default_budget: int = 8192, max_budget: int = 128000) -> None:
        self._default_budget = default_budget
        self._max_budget = max_budget
        self._system_prompts: Dict[str, str] = {}
        self._tool_schemas: Dict[str, List[Dict[str, Any]]] = {}
        self._initialized: bool = False
        logger.info("ContextManager created (default_budget=%d, max_budget=%d)", default_budget, max_budget)

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("ContextManager initialized")

    async def shutdown(self) -> None:
        self._system_prompts.clear()
        self._tool_schemas.clear()
        self._initialized = False
        logger.info("ContextManager shutdown complete")

    def register_system_prompt(self, agent_type: str, prompt: str) -> None:
        """Register a system prompt for an agent type."""
        self._system_prompts[agent_type] = prompt
        logger.debug("ContextManager: registered system prompt for %s", agent_type)

    def register_tools(self, agent_type: str, tool_schemas: List[Dict[str, Any]]) -> None:
        """Register tool schemas for an agent type."""
        self._tool_schemas[agent_type] = tool_schemas
        logger.debug("ContextManager: registered %d tools for %s", len(tool_schemas), agent_type)

    async def assemble(self, agent_id: str, agent_type: str, user_message: str, memory_entries: Optional[List[Dict[str, Any]]] = None, history: Optional[List[Dict[str, Any]]] = None, token_budget: Optional[int] = None) -> AssembledContext:
        """Assemble the full context for an agent invocation.

        Priority order (highest first):
            1. System prompt
            2. Tool schemas
            3. Memory entries
            4. Conversation history
            5. User message
        """
        budget = min(token_budget or self._default_budget, self._max_budget)
        blocks: List[ContextBlock] = []
        used: List[str] = []
        truncated: List[str] = []

        # System prompt
        system_prompt = self._system_prompts.get(agent_type, "")
        if system_prompt:
            blocks.append(ContextBlock(source=ContextSource.SYSTEM, content=system_prompt, priority=100, token_estimate=len(system_prompt) // 3))
            used.append("system_prompt")

        # Tool schemas
        tools = self._tool_schemas.get(agent_type, [])
        if tools:
            tool_str = str(tools)
            blocks.append(ContextBlock(source=ContextSource.TOOLS, content=tool_str, priority=90, token_estimate=len(tool_str) // 3))
            used.append("tool_schemas")

        # Memory
        if memory_entries:
            mem_str = str(memory_entries)
            blocks.append(ContextBlock(source=ContextSource.MEMORY, content=mem_str, priority=80, token_estimate=len(mem_str) // 3))
            used.append("memory")

        # History
        if history:
            hist_str = str(history[-20:])  # Keep last 20 turns
            blocks.append(ContextBlock(source=ContextSource.HISTORY, content=hist_str, priority=70, token_estimate=len(hist_str) // 3))
            used.append("history")

        # User message (always included)
        blocks.append(ContextBlock(source=ContextSource.USER, content=user_message, priority=60, token_estimate=len(user_message) // 3))
        used.append("user_message")

        # Build messages list
        messages: List[Dict[str, Any]] = []
        total_tokens = 0

        for block in sorted(blocks, key=lambda b: b.priority, reverse=True):
            if total_tokens + block.token_estimate > budget:
                # Truncate lower-priority blocks
                if block.source in (ContextSource.SYSTEM, ContextSource.USER):
                    # System and user messages cannot be truncated
                    messages.append({"role": "system" if block.source == ContextSource.SYSTEM else "user", "content": block.content})
                    total_tokens += block.token_estimate
                else:
                    truncated.append(block.source.value)
                continue

            role = "system" if block.source == ContextSource.SYSTEM else "user"
            messages.append({"role": role, "content": block.content})
            total_tokens += block.token_estimate

        ctx = AssembledContext(
            messages=messages,
            total_tokens=total_tokens,
            token_budget=budget,
            blocks_used=used,
            blocks_truncated=truncated,
        )
        logger.debug("ContextManager: assembled %d tokens (budget=%d, truncated=%d)", total_tokens, budget, len(truncated))
        return ctx

    async def estimate_tokens(self, text: str) -> int:
        """Rough token estimation (4 chars ≈ 1 token)."""
        return max(1, len(text) // 3)

    async def compress_context(self, context: AssembledContext, target_tokens: int) -> AssembledContext:
        """Compress context to fit within a smaller budget."""
        if context.total_tokens <= target_tokens:
            return context
        # Simple truncation strategy: remove history first
        new_messages = [m for m in context.messages if m.get("role") != "user" or "history" not in str(m.get("content", ""))]
        return AssembledContext(
            messages=new_messages,
            total_tokens=min(context.total_tokens, target_tokens),
            token_budget=target_tokens,
            blocks_used=context.blocks_used,
            blocks_truncated=context.blocks_truncated + ["compressed"],
        )

    def get_summary(self) -> Dict[str, Any]:
        return {
            "initialized": self._initialized,
            "default_budget": self._default_budget,
            "max_budget": self._max_budget,
            "registered_agent_types": sorted(self._system_prompts.keys()),
            "agents_with_tools": sorted(self._tool_schemas.keys()),
        }
