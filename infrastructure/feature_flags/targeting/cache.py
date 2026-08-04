"""
Targeting rule cache.

Provides caching for compiled rules and
evaluation results to improve performance.
Supports TTL-based expiration, version
tracking, and invalidation.

Cache layers:
    1. Compiled rule cache (AST → matcher function)
    2. Evaluation cache (context → result)
"""

from __future__ import annotations

import asyncio
import time
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from .context import TargetContext
from .rules import RuleEvaluation, TargetRule


class CompiledRuleCache:
    """
    Cache for compiled rule matcher functions.

    Stores compiled matcher functions keyed by
    rule ID to avoid repeated parsing and
    compilation overhead.
    """

    def __init__(
        self,
        max_size: int = 1000,
        ttl_seconds: int = 3600,
    ) -> None:
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._cache: OrderedDict = OrderedDict()
        self._lock = asyncio.Lock()
        self._hits = 0
        self._misses = 0

    async def get(self, rule_id: str) -> Optional[Tuple[Any, int]]:
        """
        Get a compiled matcher from cache.

        Args:
            rule_id: Rule identifier.

        Returns:
            Tuple of (matcher_fn, version) or None.
        """
        async with self._lock:
            if rule_id not in self._cache:
                self._misses += 1
                return None

            entry = self._cache[rule_id]
            matcher, version, expires_at = entry

            if datetime.utcnow() > expires_at:
                # Expired
                del self._cache[rule_id]
                self._misses += 1
                return None

            # Move to end (LRU)
            self._cache.move_to_end(rule_id)
            self._hits += 1
            return (matcher, version)

    async def put(
        self,
        rule_id: str,
        matcher: Any,
        version: int = 0,
    ) -> None:
        """
        Store a compiled matcher in cache.

        Args:
            rule_id: Rule identifier.
            matcher: Compiled matcher function.
            version: Rule version for invalidation.
        """
        async with self._lock:
            # Evict if full
            while len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)

            expires_at = datetime.utcnow() + timedelta(seconds=self._ttl)
            self._cache[rule_id] = (matcher, version, expires_at)
            self._cache.move_to_end(rule_id)

    async def invalidate(self, rule_id: str) -> None:
        """Invalidate a cached rule."""
        async with self._lock:
            self._cache.pop(rule_id, None)

    async def clear(self) -> None:
        """Clear all cached rules."""
        async with self._lock:
            self._cache.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self._hits + self._misses
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": (self._hits / total) if total > 0 else 0.0,
        }


class EvaluationCache:
    """
    Cache for rule evaluation results.

    Stores evaluation results keyed by
    (rule_id, context_hash) to avoid
    re-evaluating the same rule+context
    combination.
    """

    def __init__(
        self,
        max_size: int = 5000,
        ttl_seconds: int = 60,
    ) -> None:
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._cache: OrderedDict = OrderedDict()
        self._lock = asyncio.Lock()
        self._hits = 0
        self._misses = 0

    def _make_key(
        self,
        rule_id: str,
        context: TargetContext,
    ) -> str:
        """Create a cache key from rule and context."""
        import hashlib
        ctx_str = str(sorted(context.to_dict().items()))
        key_str = f"{rule_id}:{ctx_str}"
        return hashlib.md5(key_str.encode()).hexdigest()

    async def get(
        self,
        rule_id: str,
        context: TargetContext,
    ) -> Optional[RuleEvaluation]:
        """
        Get a cached evaluation result.

        Args:
            rule_id: Rule identifier.
            context: Evaluation context.

        Returns:
            Cached evaluation or None.
        """
        key = self._make_key(rule_id, context)

        async with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None

            entry = self._cache[key]
            evaluation, expires_at = entry

            if datetime.utcnow() > expires_at:
                del self._cache[key]
                self._misses += 1
                return None

            self._cache.move_to_end(key)
            self._hits += 1
            return evaluation

    async def put(
        self,
        rule_id: str,
        context: TargetContext,
        evaluation: RuleEvaluation,
    ) -> None:
        """
        Store an evaluation result in cache.

        Args:
            rule_id: Rule identifier.
            context: Evaluation context.
            evaluation: Evaluation result.
        """
        key = self._make_key(rule_id, context)
        expires_at = datetime.utcnow() + timedelta(seconds=self._ttl)

        async with self._lock:
            while len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)

            self._cache[key] = (evaluation, expires_at)
            self._cache.move_to_end(key)

    async def invalidate_for_rule(self, rule_id: str) -> None:
        """Invalidate all cached evaluations for a rule."""
        async with self._lock:
            keys_to_delete = [
                k for k in self._cache
                if k.startswith(rule_id)
            ]
            for k in keys_to_delete:
                del self._cache[k]

    async def clear(self) -> None:
        """Clear all cached evaluations."""
        async with self._lock:
            self._cache.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self._hits + self._misses
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": (self._hits / total) if total > 0 else 0.0,
        }