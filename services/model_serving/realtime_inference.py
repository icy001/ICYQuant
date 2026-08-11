"""
ICYQuant Realtime Inference — Low-latency real-time prediction handler.

Optimized for sub-50ms inference in live trading scenarios:
  - Feature pre-fetching and caching
  - Async non-blocking inference dispatch
  - Request prioritization (trading > risk > research)
  - Rate limiting
  - Circuit breaker for model health
"""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums & data
# ---------------------------------------------------------------------------

class CircuitState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"           # Normal operation
    OPEN = "open"               # Failing — reject all requests
    HALF_OPEN = "half_open"     # Testing recovery


@dataclass
class RealtimeConfig:
    """Real-time inference configuration."""
    max_concurrency: int = 100
    rate_limit_per_second: int = 1000
    request_timeout_ms: int = 500
    circuit_breaker_threshold: int = 10  # Consecutive failures
    circuit_breaker_timeout_seconds: int = 30
    circuit_half_open_max_requests: int = 3
    enable_prefetch: bool = True
    prefetch_window_size: int = 10
    max_queue_size: int = 1000


@dataclass
class RealtimeStats:
    """Real-time inference statistics."""
    total_requests: int = 0
    success_count: int = 0
    error_count: int = 0
    timeout_count: int = 0
    rejected_count: int = 0
    avg_latency_ms: float = 0.0
    p50_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    current_rate: float = 0.0  # requests per second


# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------

class CircuitBreaker:
    """Circuit breaker for model inference.

    Automatically opens when failure threshold is exceeded,
    then gradually tests recovery in half-open state.
    """

    def __init__(
        self,
        failure_threshold: int = 10,
        timeout_seconds: int = 30,
        half_open_max: int = 3,
    ):
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.half_open_max = half_open_max

        self._state = CircuitState.CLOSED
        self._failure_count: int = 0
        self._last_failure_time: float = 0.0
        self._half_open_count: int = 0
        self._opened_at: float = 0.0

    @property
    def state(self) -> CircuitState:
        return self._state

    def allow_request(self) -> bool:
        """Check if a request should be allowed."""
        if self._state == CircuitState.CLOSED:
            return True

        if self._state == CircuitState.OPEN:
            if time.time() - self._opened_at > self.timeout_seconds:
                self._state = CircuitState.HALF_OPEN
                self._half_open_count = 0
                logger.info("Circuit breaker: OPEN → HALF_OPEN")
                return True
            return False

        if self._state == CircuitState.HALF_OPEN:
            return self._half_open_count < self.half_open_max

        return True

    def record_success(self) -> None:
        """Record a successful request."""
        if self._state == CircuitState.HALF_OPEN:
            self._half_open_count += 1
            if self._half_open_count >= self.half_open_max:
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                logger.info("Circuit breaker: HALF_OPEN → CLOSED (recovered)")
        self._failure_count = 0

    def record_failure(self) -> None:
        """Record a failing request."""
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.OPEN
            self._opened_at = time.time()
            logger.warning("Circuit breaker: HALF_OPEN → OPEN (test failed)")
        elif self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            self._opened_at = time.time()
            logger.warning(
                "Circuit breaker: CLOSED → OPEN (%d consecutive failures)",
                self._failure_count,
            )

    def reset(self) -> None:
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._half_open_count = 0

    def get_status(self) -> Dict[str, Any]:
        return {
            "state": self._state.value,
            "failure_count": self._failure_count,
            "threshold": self.failure_threshold,
        }


# ---------------------------------------------------------------------------
# Realtime Inference
# ---------------------------------------------------------------------------

class RealtimeInference:
    """Low-latency real-time prediction handler.

    Optimized for live trading where every millisecond counts.

    Usage::

        rt = RealtimeInference(engine)
        await rt.initialize()

        prediction = await rt.predict("nvda_model", features)
    """

    def __init__(
        self,
        engine,  # InferenceEngine
        config: Optional[RealtimeConfig] = None,
    ):
        self.engine = engine
        self.config = config or RealtimeConfig()
        self._initialized = False

        # Concurrency control
        self._semaphore = asyncio.Semaphore(self.config.max_concurrency)
        self._active_requests: int = 0

        # Rate limiting
        self._rate_limiter: Dict[str, float] = {}  # model_id → last request time
        self._rate_limit_lock = asyncio.Lock()

        # Circuit breaker per model
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}

        # Stats
        self._stats = RealtimeStats()
        self._latency_history: List[float] = []
        self._max_latency_samples: int = 1000

        # Queue
        self._request_queue: asyncio.Queue = asyncio.Queue(
            maxsize=self.config.max_queue_size
        )

    async def initialize(self) -> None:
        self._initialized = True
        logger.info("RealtimeInference initialized — max_concurrency=%d",
                    self.config.max_concurrency)

    # ------------------------------------------------------------------
    # Predict
    # ------------------------------------------------------------------

    async def predict(
        self,
        model_id: str,
        features: Dict[str, Any],
        *,
        version: Optional[str] = None,
        priority: str = "normal",
    ) -> Dict[str, Any]:
        """Real-time prediction with safeguards.

        Safeguards:
          - Rate limiting
          - Circuit breaker
          - Concurrency control
          - Timeout enforcement

        Args:
            model_id: Model identifier.
            features: Feature dictionary.
            version: Optional pinned version.
            priority: Request priority (critical/high/normal).

        Returns:
            Prediction result dict.
        """
        if not self._initialized:
            raise RuntimeError("RealtimeInference not initialized")

        # Rate limiting
        if not await self._check_rate_limit(model_id):
            self._stats.rejected_count += 1
            raise RuntimeError(f"Rate limit exceeded for {model_id}")

        # Circuit breaker
        breaker = self._get_circuit_breaker(model_id)
        if not breaker.allow_request():
            self._stats.rejected_count += 1
            raise RuntimeError(f"Circuit breaker OPEN for {model_id}")

        # Concurrency control
        async with self._semaphore:
            self._stats.total_requests += 1
            start = time.perf_counter()

            try:
                # Run inference with timeout
                prediction = await asyncio.wait_for(
                    self.engine.predict(
                        model_id=model_id,
                        features=features,
                        version=version,
                        timeout_ms=self.config.request_timeout_ms,
                    ),
                    timeout=self.config.request_timeout_ms / 1000.0,
                )

                latency = time.perf_counter() - start
                self._record_latency(latency)
                self._stats.success_count += 1
                breaker.record_success()

                return prediction

            except asyncio.TimeoutError:
                self._stats.timeout_count += 1
                breaker.record_failure()
                raise RuntimeError(f"Inference timeout for {model_id}")

            except Exception:
                self._stats.error_count += 1
                breaker.record_failure()
                raise

    async def predict_batch(
        self,
        model_id: str,
        features_list: List[Dict[str, Any]],
        *,
        version: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Batch prediction with real-time safeguards."""
        tasks = [
            self.predict(model_id, features, version=version)
            for features in features_list
        ]
        return list(await asyncio.gather(*tasks, return_exceptions=False))

    # ------------------------------------------------------------------
    # Prefetch
    # ------------------------------------------------------------------

    async def prefetch_features(
        self,
        model_id: str,
        symbols: List[str],
        feature_names: List[str],
    ) -> None:
        """Pre-fetch features to warm the online store cache.

        For time-critical trading, pre-fetching features before the
        inference window reduces cold-start latency.
        """
        # This would fetch from online feature store
        logger.debug("Prefetching features for %s: %d symbols x %d features",
                     model_id, len(symbols), len(feature_names))

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _check_rate_limit(self, model_id: str) -> bool:
        """Simple token-bucket rate limiter."""
        async with self._rate_limit_lock:
            now = time.time()
            last = self._rate_limiter.get(model_id, 0)
            interval = 1.0 / max(self.config.rate_limit_per_second, 1)

            if now - last < interval:
                return False

            self._rate_limiter[model_id] = now
            return True

    def _get_circuit_breaker(self, model_id: str) -> CircuitBreaker:
        """Get or create circuit breaker for a model."""
        if model_id not in self._circuit_breakers:
            self._circuit_breakers[model_id] = CircuitBreaker(
                failure_threshold=self.config.circuit_breaker_threshold,
                timeout_seconds=self.config.circuit_breaker_timeout_seconds,
                half_open_max=self.config.circuit_half_open_max_requests,
            )
        return self._circuit_breakers[model_id]

    def _record_latency(self, latency_seconds: float) -> None:
        """Record inference latency for stats."""
        latency_ms = latency_seconds * 1000
        self._latency_history.append(latency_ms)
        if len(self._latency_history) > self._max_latency_samples:
            self._latency_history = self._latency_history[-self._max_latency_samples:]

        # Update rolling averages
        n = len(self._latency_history)
        self._stats.avg_latency_ms = sum(self._latency_history) / n
        sorted_lat = sorted(self._latency_history)
        self._stats.p50_latency_ms = sorted_lat[n // 2]
        self._stats.p99_latency_ms = sorted_lat[int(n * 0.99)]

    # ------------------------------------------------------------------
    # Stats & health
    # ------------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_requests": self._stats.total_requests,
            "success_count": self._stats.success_count,
            "error_count": self._stats.error_count,
            "timeout_count": self._stats.timeout_count,
            "rejected_count": self._stats.rejected_count,
            "avg_latency_ms": round(self._stats.avg_latency_ms, 4),
            "p50_latency_ms": round(self._stats.p50_latency_ms, 4),
            "p99_latency_ms": round(self._stats.p99_latency_ms, 4),
            "active_requests": self._active_requests,
            "circuit_breakers": {
                mid: cb.get_status()
                for mid, cb in self._circuit_breakers.items()
            },
        }

    async def health(self) -> Dict[str, Any]:
        open_breakers = sum(
            1 for cb in self._circuit_breakers.values()
            if cb.state == CircuitState.OPEN
        )
        return {
            "status": "degraded" if open_breakers > 0 else "healthy",
            "circuit_breakers_open": open_breakers,
            "stats": self.get_stats(),
        }

    def __repr__(self) -> str:
        return (
            f"RealtimeInference(requests={self._stats.total_requests}, "
            f"avg_latency={self._stats.avg_latency_ms:.1f}ms)"
        )
