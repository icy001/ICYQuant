"""Model Fallback — automatic failover when a model or provider is unavailable.

The ModelFallback engine handles graceful degradation when a model call fails.
It maintains a fallback chain per provider and automatically retries with
alternative models when the primary model is unavailable, rate-limited, or
returns errors.

Fallback strategies:
    - Same provider, cheaper model
    - Same provider, lighter model
    - Cross-provider fallback
    - Graceful degradation (reduce capabilities)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class FallbackReason(str, Enum):
    """Reasons for triggering a fallback."""
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    MODEL_OVERLOADED = "model_overloaded"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    CONTEXT_OVERFLOW = "context_overflow"
    COST_EXCEEDED = "cost_exceeded"
    UNKNOWN_ERROR = "unknown_error"


@dataclass
class FallbackEvent:
    """Record of a fallback decision."""
    event_id: str = ""
    original_model: str = ""
    fallback_model: str = ""
    reason: FallbackReason = FallbackReason.UNKNOWN_ERROR
    attempt_number: int = 0
    latency_ms: float = 0.0
    success: bool = False
    timestamp: float = field(default_factory=time.monotonic)


@dataclass
class FallbackChain:
    """Ordered list of fallback models for a primary model."""
    primary_model: str
    fallback_models: List[str] = field(default_factory=list)
    max_retries: int = 3


class ModelFallback:
    """Automatic failover engine for model invocations.

    When a model call fails, the fallback engine automatically retries with
    alternative models following the configured fallback chain.

    Usage:
        mf = ModelFallback()
        await mf.initialize()
        mf.register_chain(FallbackChain(primary="gpt-4o", fallback_models=["gpt-4o-mini", "claude-3-haiku"]))
        result = await mf.execute_with_fallback(primary_model="gpt-4o", call_fn=my_call)
    """

    def __init__(self) -> None:
        self._chains: Dict[str, FallbackChain] = {}
        self._history: List[FallbackEvent] = []
        self._max_history: int = 1000
        self._initialized: bool = False
        logger.info("ModelFallback created")

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("ModelFallback initialized")

    async def shutdown(self) -> None:
        self._chains.clear()
        self._history.clear()
        self._initialized = False
        logger.info("ModelFallback shutdown complete")

    def register_chain(self, chain: FallbackChain) -> None:
        """Register a fallback chain for a primary model."""
        self._chains[chain.primary_model] = chain
        logger.info("ModelFallback: registered chain for %s (fallbacks=%d)", chain.primary_model, len(chain.fallback_models))

    def unregister_chain(self, primary_model: str) -> bool:
        """Remove a fallback chain."""
        if primary_model in self._chains:
            del self._chains[primary_model]
            return True
        return False

    def get_chain(self, primary_model: str) -> Optional[FallbackChain]:
        """Get the fallback chain for a model."""
        return self._chains.get(primary_model)

    async def execute_with_fallback(self, primary_model: str, call_fn: Any, *args: Any, **kwargs: Any) -> Any:
        """Execute a model call with automatic fallback.

        Tries the primary model first, then falls back through the chain
        on failure. Raises the last error if all models fail.
        """
        chain = self._chains.get(primary_model, FallbackChain(primary_model=primary_model))
        models_to_try = [primary_model] + chain.fallback_models[:chain.max_retries]
        last_error: Optional[Exception] = None

        for attempt, model_id in enumerate(models_to_try):
            try:
                start = time.monotonic()
                result = await call_fn(model_id, *args, **kwargs)
                elapsed = (time.monotonic() - start) * 1000

                event = FallbackEvent(
                    event_id=f"fb_{int(time.monotonic()*1000)}",
                    original_model=primary_model,
                    fallback_model=model_id,
                    reason=FallbackReason.UNKNOWN_ERROR if attempt == 0 else FallbackReason.PROVIDER_UNAVAILABLE,
                    attempt_number=attempt,
                    latency_ms=round(elapsed, 2),
                    success=True,
                )
                self._record_event(event)
                logger.info("ModelFallback: %s succeeded on attempt %d", model_id, attempt)
                return result

            except Exception as e:
                last_error = e
                reason = self._classify_error(e)
                logger.warning("ModelFallback: %s failed (attempt %d, reason=%s): %s", model_id, attempt, reason.value, e)

                event = FallbackEvent(
                    event_id=f"fb_{int(time.monotonic()*1000)}",
                    original_model=primary_model,
                    fallback_model=model_id,
                    reason=reason,
                    attempt_number=attempt,
                    success=False,
                )
                self._record_event(event)

        raise RuntimeError(f"All fallback models exhausted for {primary_model}") from last_error

    def _classify_error(self, error: Exception) -> FallbackReason:
        """Classify an error into a fallback reason."""
        error_str = str(error).lower()
        if "rate limit" in error_str or "429" in error_str:
            return FallbackReason.RATE_LIMITED
        if "timeout" in error_str:
            return FallbackReason.TIMEOUT
        if "context" in error_str and ("length" in error_str or "token" in error_str):
            return FallbackReason.CONTEXT_OVERFLOW
        if "unavailable" in error_str or "503" in error_str:
            return FallbackReason.PROVIDER_UNAVAILABLE
        return FallbackReason.UNKNOWN_ERROR

    def _record_event(self, event: FallbackEvent) -> None:
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

    def get_fallback_stats(self, primary_model: str) -> Dict[str, Any]:
        """Get fallback statistics for a primary model."""
        events = [e for e in self._history if e.original_model == primary_model]
        total = len(events)
        successful = len([e for e in events if e.success])
        return {
            "primary_model": primary_model,
            "total_attempts": total,
            "successful": successful,
            "success_rate": successful / total if total > 0 else 0.0,
            "fallback_triggered": len([e for e in events if e.attempt_number > 0]),
        }

    def get_summary(self) -> Dict[str, Any]:
        return {
            "initialized": self._initialized,
            "registered_chains": len(self._chains),
            "total_fallback_events": len(self._history),
        }
