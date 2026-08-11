"""Token Manager — tracks and optimizes token usage across all model calls.

The TokenManager provides real-time token counting, usage tracking per
user/session/agent, and token budget enforcement. It integrates with the
ModelRouter to ensure token budgets are respected before and during calls.

Token tracking dimensions:
    - Per user
    - Per session
    - Per agent
    - Per model
    - Per time window (hourly, daily, monthly)
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class TokenUsage:
    """Token usage statistics for a dimension."""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    call_count: int = 0
    first_call: float = field(default_factory=time.monotonic)
    last_call: float = field(default_factory=time.monotonic)

    @property
    def avg_tokens_per_call(self) -> float:
        return self.total_tokens / self.call_count if self.call_count > 0 else 0.0


@dataclass
class TokenBudget:
    """Token budget configuration."""
    max_input_tokens: int = 100000
    max_output_tokens: int = 50000
    max_total_tokens: int = 150000
    max_calls: int = 1000
    window_sec: float = 86400.0  # 24 hours
    enforce: bool = True


class TokenManager:
    """Tracks and manages token usage across the AI platform.

    Provides per-user, per-session, and per-agent token tracking with
    budget enforcement. Integrates with cost management for billing.

    Usage:
        tm = TokenManager()
        await tm.initialize()
        tm.record_usage(user_id="user_1", input_tokens=500, output_tokens=200)
        usage = tm.get_user_usage("user_1")
    """

    def __init__(self) -> None:
        self._user_usage: Dict[str, TokenUsage] = {}
        self._session_usage: Dict[str, TokenUsage] = {}
        self._agent_usage: Dict[str, TokenUsage] = {}
        self._model_usage: Dict[str, TokenUsage] = {}
        self._budgets: Dict[str, TokenBudget] = {}
        self._global_usage = TokenUsage()
        self._lock = threading.Lock()
        self._initialized: bool = False
        logger.info("TokenManager created")

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("TokenManager initialized")

    async def shutdown(self) -> None:
        with self._lock:
            self._user_usage.clear()
            self._session_usage.clear()
            self._agent_usage.clear()
            self._model_usage.clear()
            self._budgets.clear()
        self._initialized = False
        logger.info("TokenManager shutdown complete")

    def record_usage(self, user_id: str = "", session_id: str = "", agent_id: str = "", model_id: str = "", input_tokens: int = 0, output_tokens: int = 0) -> None:
        """Record token usage for a model call."""
        total = input_tokens + output_tokens
        now = time.monotonic()

        with self._lock:
            self._global_usage.input_tokens += input_tokens
            self._global_usage.output_tokens += output_tokens
            self._global_usage.total_tokens += total
            self._global_usage.call_count += 1
            self._global_usage.last_call = now

            if user_id:
                self._update_usage(self._user_usage, user_id, input_tokens, output_tokens, total, now)
            if session_id:
                self._update_usage(self._session_usage, session_id, input_tokens, output_tokens, total, now)
            if agent_id:
                self._update_usage(self._agent_usage, agent_id, input_tokens, output_tokens, total, now)
            if model_id:
                self._update_usage(self._model_usage, model_id, input_tokens, output_tokens, total, now)

        logger.debug("TokenManager: recorded %d tokens (user=%s, model=%s)", total, user_id, model_id)

    def _update_usage(self, store: Dict[str, TokenUsage], key: str, input_tokens: int, output_tokens: int, total: int, now: float) -> None:
        if key not in store:
            store[key] = TokenUsage()
        u = store[key]
        u.input_tokens += input_tokens
        u.output_tokens += output_tokens
        u.total_tokens += total
        u.call_count += 1
        u.last_call = now

    def get_user_usage(self, user_id: str) -> Optional[TokenUsage]:
        return self._user_usage.get(user_id)

    def get_session_usage(self, session_id: str) -> Optional[TokenUsage]:
        return self._session_usage.get(session_id)

    def get_agent_usage(self, agent_id: str) -> Optional[TokenUsage]:
        return self._agent_usage.get(agent_id)

    def get_model_usage(self, model_id: str) -> Optional[TokenUsage]:
        return self._model_usage.get(model_id)

    def get_global_usage(self) -> TokenUsage:
        return self._global_usage

    def set_budget(self, key: str, budget: TokenBudget) -> None:
        """Set a token budget for a user or project."""
        self._budgets[key] = budget
        logger.info("TokenManager: budget set for %s (max_total=%d)", key, budget.max_total_tokens)

    def check_budget(self, key: str) -> Tuple[bool, str]:
        """Check if a budget key has remaining capacity.

        Returns (within_budget, reason).
        """
        budget = self._budgets.get(key)
        if not budget:
            return True, ""

        usage = self._user_usage.get(key)
        if not usage:
            return True, ""

        now = time.monotonic()
        if now - usage.first_call > budget.window_sec:
            return True, ""

        if budget.enforce:
            if usage.total_tokens >= budget.max_total_tokens:
                return False, f"Total token budget exceeded ({usage.total_tokens}/{budget.max_total_tokens})"
            if usage.call_count >= budget.max_calls:
                return False, f"Call count budget exceeded ({usage.call_count}/{budget.max_calls})"

        return True, ""

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for a text (rough: ~4 chars per token)."""
        return max(1, len(text) // 3)

    def get_summary(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "initialized": self._initialized,
                "global_usage": {
                    "input_tokens": self._global_usage.input_tokens,
                    "output_tokens": self._global_usage.output_tokens,
                    "total_tokens": self._global_usage.total_tokens,
                    "call_count": self._global_usage.call_count,
                },
                "unique_users": len(self._user_usage),
                "unique_sessions": len(self._session_usage),
                "unique_agents": len(self._agent_usage),
                "unique_models": len(self._model_usage),
                "active_budgets": len(self._budgets),
            }
