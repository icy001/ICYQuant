"""
Runtime feature service for lock-free reads.

Provides millisecond-level feature flag
evaluation with snapshot-based caching and
atomic reference swaps for lock-free reads.

The RuntimeFeatureService is the primary
read-side interface for application code.
All reads are lock-free and snapshot-based.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable, Dict, List, Optional

from .evaluator import FeatureEvaluator
from .models import FeatureContext
from .snapshot import FeatureSnapshot, SnapshotManager

logger = logging.getLogger(__name__)


class RuntimeFeatureService:
    """
    Lock-free runtime feature flag service.

    Provides millisecond-level evaluation
    using snapshot-based caching and atomic
    reference swaps. Read operations never
    block and never hold locks.

    Architecture:
        ┌─────────────────────────────┐
        │  RuntimeFeatureService      │
        │                             │
        │  ┌─────────────────────┐   │
        │  │  SnapshotManager    │   │
        │  │  (atomic swap)       │   │
        │  └─────────┬───────────┘   │
        │            │                 │
        │  ┌─────────▼───────────┐   │
        │  │  Current Snapshot   │   │
        │  │  (lock-free read)   │   │
        │  └─────────────────────┘   │
        │                             │
        │  ┌─────────────────────┐   │
        │  │  FeatureEvaluator   │   │
        │  │  (evaluation logic) │   │
        │  └─────────────────────┘   │
        └─────────────────────────────┘

    Usage:
        service = RuntimeFeatureService()
        await service.start(snapshot)

        # Lock-free reads
        if service.is_enabled("my.flag", context):
            ...
        value = service.evaluate("my.flag", context)
    """

    def __init__(
        self,
        evaluator: Optional[FeatureEvaluator] = None,
    ) -> None:
        """
        Initialize runtime feature service.

        Args:
            evaluator: FeatureEvaluator instance.
        """
        self._evaluator = evaluator or FeatureEvaluator()
        self._snapshot_mgr = SnapshotManager()
        self._current_flags: Dict[str, Dict[str, Any]] = {}
        self._running = False
        self._evaluation_count = 0
        self._error_count = 0
        self._total_duration_ms = 0.0
        self._cache_hits = 0
        self._cache_misses = 0

    @property
    def is_running(self) -> bool:
        """Check if the runtime service is running."""
        return self._running

    @property
    def evaluator(self) -> FeatureEvaluator:
        """Get the feature evaluator."""
        return self._evaluator

    @property
    def snapshot_manager(self) -> SnapshotManager:
        """Get the snapshot manager."""
        return self._snapshot_mgr

    async def start(
        self,
        initial_snapshot: Optional[FeatureSnapshot] = None,
    ) -> None:
        """
        Start the runtime service with an initial snapshot.

        Args:
            initial_snapshot: Initial snapshot to load.
        """
        if initial_snapshot:
            self._snapshot_mgr.activate(initial_snapshot)
            self._current_flags = initial_snapshot.flags
        self._running = True
        logger.info(
            "RuntimeFeatureService started with %d flags",
            len(self._current_flags),
        )

    async def shutdown(self) -> None:
        """Shutdown the runtime service."""
        self._running = False
        logger.info("RuntimeFeatureService shutdown")

    def is_enabled(
        self,
        key: str,
        context: Optional[FeatureContext] = None,
        default: bool = False,
    ) -> bool:
        """
        Check if a feature flag is enabled (sync, lock-free).

        This is the primary read-side interface.
        It reads directly from the current snapshot
        without any locks.

        Args:
            key: Feature flag key.
            context: Evaluation context.
            default: Default value if flag not found.

        Returns:
            True if the feature is enabled.
        """
        self._evaluation_count += 1
        start = time.perf_counter()

        try:
            # Lock-free read from current flags
            flag_data = self._current_flags.get(key)
            if flag_data is None:
                self._cache_misses += 1
                duration_ms = (time.perf_counter() - start) * 1000
                self._total_duration_ms += duration_ms
                return default

            self._cache_hits += 1

            # Check if flag is enabled
            if not flag_data.get("enabled", False):
                duration_ms = (time.perf_counter() - start) * 1000
                self._total_duration_ms += duration_ms
                return False

            # Check status
            status = flag_data.get("status", "active")
            if status in ("inactive", "archived", "deprecated"):
                duration_ms = (time.perf_counter() - start) * 1000
                self._total_duration_ms += duration_ms
                return False

            duration_ms = (time.perf_counter() - start) * 1000
            self._total_duration_ms += duration_ms
            return flag_data.get("default_value", True)

        except Exception as e:
            self._error_count += 1
            duration_ms = (time.perf_counter() - start) * 1000
            self._total_duration_ms += duration_ms
            logger.error("Runtime evaluation error for %s: %s", key, e)
            return default

    async def evaluate(
        self,
        key: str,
        context: Optional[FeatureContext] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate a feature flag with full details (async).

        Uses the FeatureEvaluator for complex
        evaluations with rules, rollouts, etc.

        Args:
            key: Feature flag key.
            context: Evaluation context.

        Returns:
            Evaluation result dictionary.
        """
        self._evaluation_count += 1
        start = time.perf_counter()

        try:
            flag_data = self._current_flags.get(key)
            if flag_data is None:
                self._cache_misses += 1
                duration_ms = (time.perf_counter() - start) * 1000
                return {
                    "key": key,
                    "value": False,
                    "reason": "flag_not_found",
                    "duration_ms": duration_ms,
                }

            self._cache_hits += 1

            # Build a minimal FeatureFlag from snapshot data
            from .models import FeatureFlag, FeatureFlagType, EvaluationStrategy

            flag = self._data_to_flag(key, flag_data)

            result = await self._evaluator.evaluate(flag, context)
            duration_ms = (time.perf_counter() - start) * 1000
            self._total_duration_ms += duration_ms

            return {
                "key": key,
                "value": result.value,
                "enabled": result.enabled,
                "result": result.result.value,
                "reason": result.reason,
                "matched_rule_id": result.matched_rule_id,
                "duration_ms": duration_ms,
            }

        except Exception as e:
            self._error_count += 1
            duration_ms = (time.perf_counter() - start) * 1000
            self._total_duration_ms += duration_ms
            logger.error("Runtime evaluation error for %s: %s", key, e)
            return {
                "key": key,
                "value": False,
                "reason": f"error: {e}",
                "duration_ms": duration_ms,
            }

    def get_value(
        self,
        key: str,
        context: Optional[FeatureContext] = None,
        default: Any = None,
    ) -> Any:
        """
        Get a feature flag's value (sync, lock-free).

        Args:
            key: Feature flag key.
            context: Evaluation context.
            default: Default value if not found.

        Returns:
            Flag value.
        """
        flag_data = self._current_flags.get(key)
        if flag_data is None:
            return default

        if not flag_data.get("enabled", False):
            return default

        return flag_data.get("default_value", default)

    def get_flag(
        self,
        key: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get a flag's data from the current snapshot.

        Args:
            key: Feature flag key.

        Returns:
            Flag data dictionary or None.
        """
        return self._current_flags.get(key)

    def list_flags(
        self,
        tag: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        List all flags from the current snapshot.

        Args:
            tag: Filter by tag.

        Returns:
            List of flag data dictionaries.
        """
        results = []
        for key, data in self._current_flags.items():
            if tag and tag not in data.get("tags", []):
                continue
            item = dict(data)
            item["key"] = key
            results.append(item)
        return results

    def refresh(
        self,
        flags: Dict[str, Dict[str, Any]],
    ) -> None:
        """
        Refresh the runtime with new flag data.

        This performs an atomic swap of the
        current flags dictionary. All subsequent
        reads will see the new data.

        Args:
            flags: New flag data dictionary.
        """
        self._current_flags = dict(flags)
        snap = self._snapshot_mgr.create_snapshot(flags)
        self._snapshot_mgr.activate(snap)
        logger.info(
            "Runtime refreshed with %d flags (v%d)",
            len(flags),
            snap.version,
        )

    def _data_to_flag(
        self,
        key: str,
        data: Dict[str, Any],
    ) -> Any:
        """Convert snapshot data to FeatureFlag object."""
        from .constants import EvaluationStrategy, FeatureFlagType, FlagStatus
        from .models import FeatureFlag, FeatureRule

        rules = []
        for rule_data in data.get("rules", []):
            rules.append(FeatureRule(
                rule_id=rule_data.get("rule_id", ""),
                priority=rule_data.get("priority", 0),
                condition=rule_data.get("condition", "true"),
                value=rule_data.get("value", True),
                enabled=rule_data.get("enabled", True),
            ))

        return FeatureFlag(
            key=key,
            enabled=data.get("enabled", True),
            description=data.get("description", ""),
            flag_type=FeatureFlagType(data.get("flag_type", "boolean")),
            strategy=EvaluationStrategy(data.get("strategy", "static")),
            default_value=data.get("default_value", True),
            tags=frozenset(data.get("tags", [])),
            metadata=data.get("metadata", {}),
            rules=rules,
            status=FlagStatus(data.get("status", "active")),
            owner=data.get("owner", "system"),
        )

    def get_current_version(self) -> int:
        """Get current snapshot version."""
        return self._snapshot_mgr.get_version()

    def get_snapshot(self) -> Optional[FeatureSnapshot]:
        """Get current snapshot."""
        return self._snapshot_mgr.get_current()

    def get_stats(self) -> Dict[str, Any]:
        """Get runtime service statistics."""
        total = self._evaluation_count
        avg_duration = self._total_duration_ms / total if total > 0 else 0.0
        return {
            "running": self._running,
            "flags_count": len(self._current_flags),
            "snapshot_version": self._snapshot_mgr.get_version(),
            "evaluations": self._evaluation_count,
            "errors": self._error_count,
            "avg_duration_ms": avg_duration,
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "hit_ratio": (
                self._cache_hits / (self._cache_hits + self._cache_misses)
                if (self._cache_hits + self._cache_misses) > 0
                else 0.0
            ),
            "snapshot_stats": self._snapshot_mgr.get_stats(),
        }

    def reset_stats(self) -> None:
        """Reset all runtime statistics."""
        self._evaluation_count = 0
        self._error_count = 0
        self._total_duration_ms = 0.0
        self._cache_hits = 0
        self._cache_misses = 0
