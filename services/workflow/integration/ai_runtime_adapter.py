"""AI Runtime Adapter — AI / LLM reasoning workflow orchestration.

Enables::

    LLM → Reasoning → Workflow → Tool Call → Execution

Provides unified orchestration for AI Agent scenarios, where LLM reasoning
is embedded in workflow nodes that can call tools and external services.

Key capabilities:
* LLM prompt and reasoning nodes in workflows
* Tool-calling integration (function calling, API invocation)
* Chain-of-thought / ReAct agent patterns
* Model routing and fallback
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class AIAction(str, Enum):
    """Types of AI actions in a workflow."""

    REASON = "reason"
    GENERATE = "generate"
    CLASSIFY = "classify"
    SUMMARIZE = "summarize"
    TOOL_CALL = "tool_call"
    DECISION = "decision"


class AIModel(str, Enum):
    """AI model identifiers."""

    GPT4 = "gpt-4"
    GPT4O = "gpt-4o"
    CLAUDE3 = "claude-3-opus"
    GEMINI = "gemini-pro"
    LOCAL = "local"


@dataclass
class AIRequest:
    """A request to the AI runtime from a workflow node."""

    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    action: AIAction = AIAction.REASON
    model: AIModel = AIModel.GPT4O
    prompt: str = ""
    context: Dict[str, Any] = field(default_factory=dict)
    tools: List[str] = field(default_factory=list)
    temperature: float = 0.7
    max_tokens: int = 4096
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "action": self.action.value,
            "model": self.model.value,
            "prompt": self.prompt,
            "tools": self.tools,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }


@dataclass
class AIResponse:
    """The result of an AI runtime call."""

    request_id: str
    content: str = ""
    reasoning: str = ""
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    model_used: AIModel = AIModel.GPT4O
    tokens_used: int = 0
    latency_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_success(self) -> bool:
        return self.error is None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "content": self.content,
            "reasoning": self.reasoning,
            "tool_calls": self.tool_calls,
            "model_used": self.model_used.value,
            "tokens_used": self.tokens_used,
            "latency_ms": self.latency_ms,
        }


class AIRuntimeAdapter:
    """Bridges workflow nodes with the AI/LLM runtime.

    Usage::

        adapter = AIRuntimeAdapter()
        await adapter.start()
        req = AIRequest(action=AIAction.REASON, prompt="Analyze market conditions")
        resp = await adapter.invoke(req)
    """

    def __init__(self) -> None:
        self._lock = __import__("threading").RLock()
        self._started = False
        self._history: List[AIResponse] = []
        self._max_history = 10000
        self._tool_handlers: Dict[str, Callable] = {}
        self._on_response_callbacks: List[Callable] = []

    async def start(self) -> None:
        self._started = True
        logger.info("AIRuntimeAdapter: started")

    async def stop(self) -> None:
        self._started = False
        logger.info("AIRuntimeAdapter: stopped")

    async def invoke(self, request: AIRequest) -> AIResponse:
        """Invoke the AI runtime with a workflow request."""
        import time
        start = time.monotonic()
        logger.info("AIRuntimeAdapter: invoking %s (model=%s, action=%s)", request.request_id, request.model.value, request.action.value)

        # In production: route to actual LLM service
        response = AIResponse(
            request_id=request.request_id,
            content=f"[AI response for: {request.action.value}]",
            model_used=request.model,
            latency_ms=(time.monotonic() - start) * 1000,
        )

        with self._lock:
            self._history.append(response)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]

        for cb in self._on_response_callbacks:
            try:
                cb(request, response)
            except Exception:
                logger.exception("AIRuntimeAdapter: response callback error")

        return response

    async def invoke_with_tools(self, request: AIRequest) -> AIResponse:
        """Invoke with tool-calling support."""
        response = await self.invoke(request)
        # Execute tool calls
        for tool_call in response.tool_calls:
            tool_name = tool_call.get("name", "")
            handler = self._tool_handlers.get(tool_name)
            if handler:
                try:
                    result = handler(tool_call.get("arguments", {}))
                    tool_call["result"] = result
                except Exception as e:
                    tool_call["error"] = str(e)
        return response

    def register_tool(self, name: str, handler: Callable) -> None:
        """Register a tool handler for AI tool-calling."""
        self._tool_handlers[name] = handler

    async def get_response(self, request_id: str) -> Optional[AIResponse]:
        with self._lock:
            for r in reversed(self._history):
                if r.request_id == request_id:
                    return r
            return None

    async def get_history(self, limit: int = 100) -> List[AIResponse]:
        with self._lock:
            return list(self._history[-limit:])

    def on_response(self, callback: Callable) -> None:
        self._on_response_callbacks.append(callback)

    def health_report(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_invocations": len(self._history),
                "registered_tools": len(self._tool_handlers),
                "tools": list(self._tool_handlers.keys()),
            }
