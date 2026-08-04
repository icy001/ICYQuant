"""
Hot reload engine.

Implements the configuration reload pipeline:
    Load → Merge → Validate → Build Snapshot → Atomic Swap → Publish Event

Guarantees:
- Zero downtime (atomic snapshot swap)
- Lock-free reads during reload
- No partial configuration updates
- Validation before activation
"""

from __future__ import annotations

import copy
import time
import threading
from typing import Any, Callable, Dict, List, Optional

from .atomic import AtomicSnapshotManager
from .snapshot import DynamicSnapshot


class HotReloadEngine:
    """
    Hot reload engine for configuration.

    Orchestrates the full reload pipeline:
    1. Load configuration from all sources
    2. Merge sources with priority ordering
    3. Validate the merged configuration
    4. Build a new immutable snapshot
    5. Atomically swap the snapshot
    6. Publish change events

    Usage:
        engine = HotReloadEngine()

        # Register data loaders
        engine.add_loader("yaml", load_yaml_config)
        engine.add_loader("env", load_env_config)

        # Reload
        result = engine.reload()
    """

    def __init__(
        self,
        snapshot_manager: Optional[AtomicSnapshotManager] = None,
        merge_strategy: str = "recursive",
    ) -> None:
        """
        Initialize hot reload engine.

        Args:
            snapshot_manager: Atomic snapshot manager.
            merge_strategy: Merge strategy for combining sources.
        """
        self._snapshot_manager = snapshot_manager or AtomicSnapshotManager()
        self._merge_strategy = merge_strategy

        # Source loaders: {name: (loader_func, priority)}
        self._loaders: Dict[str, tuple] = {}

        # Pre-processing hooks
        self._pre_hooks: List[Callable] = []
        self._post_hooks: List[Callable] = []
        self._validate_hooks: List[Callable] = []

        # Metrics
        self._reload_count = 0
        self._success_count = 0
        self._failure_count = 0
        self._last_duration = 0.0
        self._lock = threading.Lock()

    @property
    def snapshot_manager(
        self,
    ) -> AtomicSnapshotManager:
        """Get atomic snapshot manager."""
        return self._snapshot_manager

    @property
    def reload_stats(
        self,
    ) -> Dict[str, Any]:
        """Get reload statistics."""
        return {
            "total": self._reload_count,
            "success": self._success_count,
            "failure": self._failure_count,
            "last_duration": self._last_duration,
        }

    def add_loader(
        self,
        name: str,
        loader_func: Callable,
        priority: int = 50,
    ) -> None:
        """
        Register a configuration source loader.

        Args:
            name: Source name.
            loader_func: Callable that returns Dict[str, Any].
            priority: Source priority (higher = more important).
        """
        self._loaders[name] = (loader_func, priority)

    def add_pre_hook(
        self,
        hook: Callable,
    ) -> None:
        """Add a pre-reload hook (runs before loading)."""
        self._pre_hooks.append(hook)

    def add_post_hook(
        self,
        hook: Callable,
    ) -> None:
        """Add a post-reload hook (runs after successful reload)."""
        self._post_hooks.append(hook)

    def add_validate_hook(
        self,
        hook: Callable,
    ) -> None:
        """Add a validation hook."""
        self._validate_hooks.append(hook)

    def reload(
        self,
        operator: str = "system",
        reason: str = "",
        force: bool = False,
    ) -> ReloadResult:
        """
        Execute the full reload pipeline.

        Pipeline:
        1. Run pre-hooks
        2. Load from all sources
        3. Merge with priority ordering
        4. Validate merged configuration
        5. Build new snapshot
        6. Atomically swap
        7. Run post-hooks

        Args:
            operator: Who triggered the reload.
            reason: Reason for the reload.
            force: Force reload even if unchanged.

        Returns:
            ReloadResult with status and details.
        """
        start_time = time.time()

        with self._lock:
            self._reload_count += 1

            try:
                # Step 1: Pre-hooks
                for hook in self._pre_hooks:
                    hook()

                # Step 2: Load from all sources
                source_data = self._load_all_sources()

                # Step 3: Merge
                merged = self._merge_sources(source_data)

                if not force and self._is_unchanged(merged):
                    # No change, skip reload
                    duration = time.time() - start_time
                    self._last_duration = duration
                    self._success_count += 1
                    return ReloadResult(
                        success=True,
                        status="unchanged",
                        duration=duration,
                        sources_used=list(self._loaders.keys()),
                    )

                # Step 4: Validate
                validation_errors = self._run_validation(merged)
                if validation_errors:
                    duration = time.time() - start_time
                    self._last_duration = duration
                    self._failure_count += 1
                    return ReloadResult(
                        success=False,
                        status="validation_failed",
                        duration=duration,
                        errors=validation_errors,
                    )

                # Step 5: Build new snapshot
                current = self._snapshot_manager.current
                new_snapshot = DynamicSnapshot(
                    values=merged,
                    environment=current.environment if current else "development",
                    sources_used=list(self._loaders.keys()),
                    operator=operator,
                    reason=reason or "manual reload",
                    parent_version=current.version if current else None,
                )

                # Step 6: Atomic swap
                self._snapshot_manager.activate(new_snapshot)

                # Step 7: Post-hooks
                for hook in self._post_hooks:
                    hook(new_snapshot)

                duration = time.time() - start_time
                self._last_duration = duration
                self._success_count += 1

                return ReloadResult(
                    success=True,
                    status="reloaded",
                    duration=duration,
                    sources_used=list(self._loaders.keys()),
                    new_version=new_snapshot.version,
                    changed_keys=current.diff_keys(new_snapshot) if current else [],
                )

            except Exception as e:
                duration = time.time() - start_time
                self._last_duration = duration
                self._failure_count += 1
                return ReloadResult(
                    success=False,
                    status="error",
                    duration=duration,
                    errors=[str(e)],
                )

    def _load_all_sources(
        self,
    ) -> Dict[str, Dict[str, Any]]:
        """Load configuration from all registered sources."""
        result: Dict[str, Dict[str, Any]] = {}

        for name, (loader_func, _) in self._loaders.items():
            try:
                data = loader_func()
                if data and isinstance(data, dict):
                    result[name] = data
            except Exception:
                # Skip failed sources
                pass

        return result

    def _merge_sources(
        self,
        source_data: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Merge source data with priority ordering.

        Higher priority sources override lower priority ones.

        Args:
            source_data: Data from all sources.

        Returns:
            Merged configuration.
        """
        # Sort sources by priority (lowest first)
        sorted_sources = sorted(
            self._loaders.items(),
            key=lambda x: x[1][1],
        )

        merged: Dict[str, Any] = {}

        for name, _ in sorted_sources:
            data = source_data.get(name, {})
            if self._merge_strategy == "recursive":
                merged = self._recursive_merge(merged, data)
            else:
                merged.update(copy.deepcopy(data))

        return merged

    @staticmethod
    def _recursive_merge(
        base: Dict[str, Any],
        override: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Recursively merge two dictionaries.

        Nested dicts are merged; other values are overridden.

        Args:
            base: Base dictionary.
            override: Override dictionary.

        Returns:
            Merged dictionary.
        """
        result = copy.deepcopy(base)

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = HotReloadEngine._recursive_merge(result[key], value)
            else:
                result[key] = copy.deepcopy(value)

        return result

    def _is_unchanged(
        self,
        new_values: Dict[str, Any],
    ) -> bool:
        """Check if configuration is unchanged."""
        current = self._snapshot_manager.current
        if current is None:
            return False

        return current.values == new_values

    def _run_validation(
        self,
        data: Dict[str, Any],
    ) -> List[str]:
        """Run all validation hooks."""
        errors: List[str] = []

        for hook in self._validate_hooks:
            try:
                result = hook(data)
                if result:
                    if isinstance(result, list):
                        errors.extend(result)
                    elif isinstance(result, str):
                        errors.append(result)
            except Exception as e:
                errors.append(f"Validation error: {e}")

        return errors


class ReloadResult:
    """
    Result of a reload operation.

    Attributes:
        success: Whether reload was successful.
        status: Status string (reloaded, unchanged, validation_failed, error).
        duration: Duration in seconds.
        errors: List of error messages.
        sources_used: List of source names used.
        new_version: New snapshot version.
        changed_keys: List of keys that changed.
    """

    def __init__(
        self,
        success: bool,
        status: str,
        duration: float,
        errors: Optional[List[str]] = None,
        sources_used: Optional[List[str]] = None,
        new_version: Optional[int] = None,
        changed_keys: Optional[List[str]] = None,
    ) -> None:
        self.success = success
        self.status = status
        self.duration = duration
        self.errors = errors or []
        self.sources_used = sources_used or []
        self.new_version = new_version
        self.changed_keys = changed_keys or []

    def to_dict(
        self,
    ) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "status": self.status,
            "duration": self.duration,
            "errors": self.errors,
            "sources_used": self.sources_used,
            "new_version": self.new_version,
            "changed_keys": self.changed_keys,
        }
