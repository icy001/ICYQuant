"""
ICYQuant Prediction Service — Unified prediction API layer.

Wraps the inference engine with caching, retry, timeout, and
consistent response formatting. This is the primary interface
for external consumers (strategy, risk, AI agents).
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from .inference_engine import InferenceEngine

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class PredictionConfig:
    """Prediction service configuration."""
    max_retries: int = 2
    base_retry_delay_ms: float = 100.0
    max_retry_delay_ms: float = 2000.0
    cache_ttl_seconds: int = 60
    enable_cache: bool = True
    max_cache_size: int = 10000


# ---------------------------------------------------------------------------
# Prediction Service
# ---------------------------------------------------------------------------

class PredictionService:
    """Unified prediction service.

    Provides:
      - Prediction caching (LRU, TTL-based)
      - Automatic retry with exponential backoff
      - Consistent response formatting
      - Batch prediction with pipelining
      - Request deduplication
    """

    def __init__(
        self,
        engine: "InferenceEngine",
        cache_ttl: int = 60,
        config: Optional[PredictionConfig] = None,
    ):
        self.engine = engine
        self.config = config or PredictionConfig(cache_ttl_seconds=cache_ttl)

        # Simple in-memory cache: cache_key → (timestamp, result)
        self._cache: Dict[str, tuple[float, Dict[str, Any]]] = {}
        self._cache_lock = asyncio.Lock()

        # Deduplication: in-flight requests
        self._in_flight: Dict[str, asyncio.Future] = {}

        self._initialized = False

        # Stats
        self._total_requests: int = 0
        self._cache_hits: int = 0
        self._retry_count: int = 0

    async def initialize(self) -> None:
        self._initialized = True
        logger.info("PredictionService initialized — cache_ttl=%ds", self.config.cache_ttl_seconds)

    # ------------------------------------------------------------------
    # Predict
    # ------------------------------------------------------------------

    async def predict(
        self,
        model_id: str,
        features: Dict[str, Any],
        *,
        version: Optional[str] = None,
        timeout_ms: Optional[int] = None,
        use_cache: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Predict with caching, retry, and timeout.

        Args:
            model_id: Model identifier.
            features: Feature dictionary.
            version: Optional pinned version.
            timeout_ms: Inference timeout.
            use_cache: Override cache behavior.

        Returns:
            Standard prediction response dict.
        """
        self._total_requests += 1

        # Cache lookup
        if (use_cache is None and self.config.enable_cache) or use_cache:
            cache_key = self._make_cache_key(model_id, version, features)
            cached = await self._cache_get(cache_key)
            if cached is not None:
                self._cache_hits += 1
                return cached

        # Deduplicate concurrent requests
        dedup_key = self._make_cache_key(model_id, version, features)
        if dedup_key in self._in_flight:
            logger.debug("Dedup request for %s", model_id)
            return await self._in_flight[dedup_key]

        # Create in-flight tracker
        future: asyncio.Future = asyncio.get_running_loop().create_future()
        self._in_flight[dedup_key] = future

        try:
            result = await self._predict_with_retry(
                model_id=model_id,
                features=features,
                version=version,
                timeout_ms=timeout_ms,
            )

            # Cache successful results
            if self.config.enable_cache and result.get("status") == "success":
                await self._cache_set(dedup_key, result)

            future.set_result(result)
            return result

        except Exception as exc:
            future.set_exception(exc)
            raise
        finally:
            self._in_flight.pop(dedup_key, None)

    async def predict_batch(
        self,
        model_id: str,
        features_list: List[Dict[str, Any]],
        *,
        version: Optional[str] = None,
        timeout_ms: Optional[int] = None,
        max_concurrency: int = 50,
    ) -> List[Dict[str, Any]]:
        """Batch prediction with concurrency control.

        Args:
            model_id: Model identifier.
            features_list: List of feature dictionaries.
            version: Optional pinned version.
            timeout_ms: Per-inference timeout.
            max_concurrency: Maximum concurrent inferences.

        Returns:
            Ordered list of prediction dicts.
        """
        semaphore = asyncio.Semaphore(max_concurrency)

        async def bounded_predict(features: Dict[str, Any]) -> Dict[str, Any]:
            async with semaphore:
                return await self.predict(
                    model_id=model_id,
                    features=features,
                    version=version,
                    timeout_ms=timeout_ms,
                    use_cache=False,  # Disable cache for batch
                )

        tasks = [bounded_predict(f) for f in features_list]
        return list(await asyncio.gather(*tasks, return_exceptions=False))

    # ------------------------------------------------------------------
    # Retry
    # ------------------------------------------------------------------

    async def _predict_with_retry(
        self,
        model_id: str,
        features: Dict[str, Any],
        version: Optional[str] = None,
        timeout_ms: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Run inference with exponential backoff retry."""
        last_error: Optional[Exception] = None

        for attempt in range(self.config.max_retries + 1):
            try:
                return await self.engine.predict(
                    model_id=model_id,
                    features=features,
                    version=version,
                    timeout_ms=timeout_ms,
                )
            except Exception as exc:
                last_error = exc
                if attempt < self.config.max_retries:
                    delay = min(
                        self.config.base_retry_delay_ms * (2 ** attempt),
                        self.config.max_retry_delay_ms,
                    )
                    self._retry_count += 1
                    logger.warning(
                        "Retry %d/%d for %s after %.0fms: %s",
                        attempt + 1, self.config.max_retries,
                        model_id, delay, exc,
                    )
                    await asyncio.sleep(delay / 1000.0)

        raise last_error  # type: ignore[misc]

    # ------------------------------------------------------------------
    # Cache
    # ------------------------------------------------------------------

    @staticmethod
    def _make_cache_key(
        model_id: str,
        version: Optional[str],
        features: Dict[str, Any],
    ) -> str:
        """Create a deterministic cache key."""
        # Use sorted feature keys for deterministic hashing
        feature_str = ",".join(
            f"{k}={features[k]}" for k in sorted(features.keys())
        )
        return f"{model_id}:{version or 'latest'}:{hash(feature_str)}"

    async def _cache_get(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached prediction if valid."""
        async with self._cache_lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            timestamp, result = entry
            if time.time() - timestamp > self.config.cache_ttl_seconds:
                del self._cache[key]
                return None
            return result

    async def _cache_set(self, key: str, result: Dict[str, Any]) -> None:
        """Set cache entry."""
        async with self._cache_lock:
            # Evict oldest if at capacity
            if len(self._cache) >= self.config.max_cache_size:
                oldest = min(self._cache.items(), key=lambda x: x[1][0])
                del self._cache[oldest[0]]

            self._cache[key] = (time.time(), result)

    async def clear_cache(self) -> int:
        """Clear all cached predictions."""
        async with self._cache_lock:
            count = len(self._cache)
            self._cache.clear()
            return count

    # ------------------------------------------------------------------
    # Health & stats
    # ------------------------------------------------------------------

    async def health(self) -> Dict[str, Any]:
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "total_requests": self._total_requests,
            "cache_hits": self._cache_hits,
            "cache_size": len(self._cache),
            "retry_count": self._retry_count,
            "cache_hit_rate": (
                self._cache_hits / max(self._total_requests, 1)
            ),
        }

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "requests": self._total_requests,
            "cache_hits": self._cache_hits,
            "retries": self._retry_count,
        }

    def __repr__(self) -> str:
        return (
            f"PredictionService(requests={self._total_requests}, "
            f"cache_hit_rate={self._cache_hits / max(self._total_requests, 1):.1%})"
        )
