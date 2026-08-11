"""
ICYQuant Inference Timeout — Timeout management for model inference.

Provides:
  - Per-request timeout enforcement
  - Global timeout policies per model
  - Timeout tier configuration (fast/standard/batch)
  - Timeout monitoring and alerting
  - Graceful timeout handling with partial results
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Enums & data
# ---------------------------------------------------------------------------

class TimeoutTier(str, Enum):
    """Timeout configuration tiers."""
    REALTIME = "realtime"       # < 100ms, for live trading
    STANDARD = "standard"       # < 1s, for normal predictions
    EXTENDED = "extended"       # < 5s, for complex models
    BATCH = "batch"             # < 30s, for batch processing
    BACKGROUND = "background"   # < 120s, for research


@dataclass
class TimeoutPolicy:
    """Timeout policy configuration."""
    tier: TimeoutTier
    default_timeout_ms: int
    max_timeout_ms: int
    on_timeout: str = "raise"  # raise | default | retry
    default_value: Any = None  # Used when on_timeout = "default"


# Default timeout tier configs
DEFAULT_TIMEOUT_POLICIES: Dict[TimeoutTier, TimeoutPolicy] = {
    TimeoutTier.REALTIME: TimeoutPolicy(
        tier=TimeoutTier.REALTIME,
        default_timeout_ms=100,
        max_timeout_ms=500,
        on_timeout="raise",
    ),
    TimeoutTier.STANDARD: TimeoutPolicy(
        tier=TimeoutTier.STANDARD,
        default_timeout_ms=1000,
        max_timeout_ms=5000,
        on_timeout="raise",
    ),
    TimeoutTier.EXTENDED: TimeoutPolicy(
        tier=TimeoutTier.EXTENDED,
        default_timeout_ms=5000,
        max_timeout_ms=15000,
        on_timeout="raise",
    ),
    TimeoutTier.BATCH: TimeoutPolicy(
        tier=TimeoutTier.BATCH,
        default_timeout_ms=30000,
        max_timeout_ms=120000,
        on_timeout="default",
    ),
    TimeoutTier.BACKGROUND: TimeoutPolicy(
        tier=TimeoutTier.BACKGROUND,
        default_timeout_ms=120000,
        max_timeout_ms=600000,
        on_timeout="default",
    ),
}


@dataclass
class TimeoutStats:
    """Timeout monitoring statistics."""
    total_calls: int = 0
    timeouts: int = 0
    successes: int = 0
    avg_duration_ms: float = 0.0
    total_duration_ms: float = 0.0


# ---------------------------------------------------------------------------
# Timeout Manager
# ---------------------------------------------------------------------------

class TimeoutManager:
    """Manages timeout policies and enforcement for inference calls.

    Usage::

        manager = TimeoutManager()
        manager.set_model_policy("nvda_model", TimeoutTier.REALTIME)

        try:
            result = await manager.execute_with_timeout(
                "nvda_model",
                engine.predict("nvda_model", features),
            )
        except asyncio.TimeoutError:
            logger.error("Inference timed out")
    """

    def __init__(self):
        self._initialized = False

        # Global default policy
        self._global_policy: TimeoutTier = TimeoutTier.STANDARD

        # Per-model policy overrides: model_id → TimeoutTier
        self._model_policies: Dict[str, TimeoutTier] = {}

        # Per-model stats
        self._stats: Dict[str, TimeoutStats] = {}

        # Callbacks
        self._on_timeout_callbacks: List[Callable[[str, float], None]] = []

    async def initialize(self) -> None:
        self._initialized = True
        logger.info("TimeoutManager initialized — global tier=%s",
                    self._global_policy.value)

    # ------------------------------------------------------------------
    # Policy configuration
    # ------------------------------------------------------------------

    def set_global_policy(self, tier: TimeoutTier) -> None:
        """Set the default timeout tier for all models."""
        self._global_policy = tier

    def set_model_policy(self, model_id: str, tier: TimeoutTier) -> None:
        """Set timeout tier for a specific model."""
        self._model_policies[model_id] = tier

    def get_model_policy(self, model_id: str) -> TimeoutPolicy:
        """Get the effective timeout policy for a model."""
        tier = self._model_policies.get(model_id, self._global_policy)
        return DEFAULT_TIMEOUT_POLICIES[tier]

    def get_timeout_ms(self, model_id: str, override: Optional[int] = None) -> int:
        """Get effective timeout in milliseconds."""
        if override is not None:
            return override
        policy = self.get_model_policy(model_id)
        return policy.default_timeout_ms

    # ------------------------------------------------------------------
    # Timeout enforcement
    # ------------------------------------------------------------------

    async def execute_with_timeout(
        self,
        model_id: str,
        coro: Coroutine[Any, Any, T],
        timeout_ms: Optional[int] = None,
    ) -> T:
        """Execute a coroutine with timeout enforcement.

        Args:
            model_id: Model identifier (for policy lookup).
            coro: The inference coroutine.
            timeout_ms: Optional override timeout.

        Returns:
            Result of the coroutine.
        """
        policy = self.get_model_policy(model_id)
        effective_timeout = timeout_ms or policy.default_timeout_ms

        # Ensure within max
        effective_timeout = min(effective_timeout, policy.max_timeout_ms)

        # Track stats
        if model_id not in self._stats:
            self._stats[model_id] = TimeoutStats()
        stats = self._stats[model_id]
        stats.total_calls += 1

        start = datetime.now(timezone.utc)

        try:
            result = await asyncio.wait_for(
                coro,
                timeout=effective_timeout / 1000.0,
            )

            # Success
            duration = (datetime.now(timezone.utc) - start).total_seconds() * 1000
            stats.successes += 1
            stats.total_duration_ms += duration
            stats.avg_duration_ms = stats.total_duration_ms / max(stats.successes, 1)

            return result

        except asyncio.TimeoutError:
            stats.timeouts += 1
            duration = effective_timeout

            # Notify callbacks
            for cb in self._on_timeout_callbacks:
                try:
                    cb(model_id, duration)
                except Exception:
                    logger.exception("Timeout callback error")

            # Handle per policy
            if policy.on_timeout == "default" and policy.default_value is not None:
                logger.warning(
                    "Inference timeout for %s (%.0fms) — returning default",
                    model_id, duration,
                )
                return policy.default_value

            # Log and re-raise
            logger.error(
                "Inference timeout for %s after %.0fms (tier=%s)",
                model_id, duration, policy.tier.value,
            )
            raise

    async def execute_graceful(
        self,
        model_id: str,
        coro: Coroutine[Any, Any, T],
        timeout_ms: Optional[int] = None,
        fallback: Optional[T] = None,
    ) -> T:
        """Execute with timeout, returning fallback instead of raising.

        Args:
            model_id: Model identifier.
            coro: Inference coroutine.
            timeout_ms: Timeout override.
            fallback: Value to return on timeout.

        Returns:
            Result or fallback.
        """
        try:
            return await self.execute_with_timeout(
                model_id=model_id,
                coro=coro,
                timeout_ms=timeout_ms,
            )
        except asyncio.TimeoutError:
            return fallback  # type: ignore[return-value]
        except Exception:
            raise

    # ------------------------------------------------------------------
    # Async context manager
    # ------------------------------------------------------------------

    @asynccontextmanager
    async def timeout_context(
        self,
        model_id: str,
        timeout_ms: Optional[int] = None,
    ):
        """Context manager for timeout-enforced inference.

        Usage::

            async with timeout_manager.timeout_context("nvda_model", 500):
                result = await engine.predict("nvda_model", features)
        """
        try:
            yield
        except asyncio.TimeoutError:
            policy = self.get_model_policy(model_id)
            logger.warning("Timeout in context for %s (tier=%s)",
                          model_id, policy.tier.value)
            raise

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def on_timeout(self, callback: Callable[[str, float], None]) -> None:
        """Register a timeout notification callback."""
        self._on_timeout_callbacks.append(callback)

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self, model_id: Optional[str] = None) -> Dict[str, Any]:
        """Get timeout statistics."""
        if model_id:
            stats = self._stats.get(model_id)
            if stats is None:
                return {}
            return {
                "model_id": model_id,
                "total_calls": stats.total_calls,
                "timeouts": stats.timeouts,
                "timeout_rate": round(
                    stats.timeouts / max(stats.total_calls, 1), 4
                ),
                "avg_duration_ms": round(stats.avg_duration_ms, 2),
            }

        return {
            model_id: {
                "total_calls": s.total_calls,
                "timeouts": s.timeouts,
                "timeout_rate": round(s.timeouts / max(s.total_calls, 1), 4),
            }
            for model_id, s in self._stats.items()
        }

    def get_global_timeout_rate(self) -> float:
        """Get overall timeout rate across all models."""
        total = sum(s.total_calls for s in self._stats.values())
        timeouts = sum(s.timeouts for s in self._stats.values())
        return timeouts / max(total, 1)

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health(self) -> Dict[str, Any]:
        timeout_rate = self.get_global_timeout_rate()
        return {
            "status": (
                "degraded" if timeout_rate > 0.05 else "healthy"
            ),
            "global_tier": self._global_policy.value,
            "models_tracked": len(self._stats),
            "global_timeout_rate": round(timeout_rate, 4),
            "stats": self.get_stats(),
        }

    def __repr__(self) -> str:
        return (
            f"TimeoutManager(tier={self._global_policy.value}, "
            f"models={len(self._stats)})"
        )
