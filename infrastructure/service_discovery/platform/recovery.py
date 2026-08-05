"""Platform recovery for ICYQuant service discovery.

Provides ``PlatformRecovery`` for disaster recovery workflows
including registry failure recovery, snapshot-based restore,
and automatic recovery strategies.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .runtime_context import DiscoveryContext

logger = logging.getLogger(__name__)


class RecoveryStrategy:
    """Base class for recovery strategies."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.success_count = 0
        self.failure_count = 0

    async def execute(
        self, context: DiscoveryContext
    ) -> Dict[str, Any]:
        raise NotImplementedError


class PlatformRecovery:
    """Disaster recovery for the discovery platform.

    Manages registry failure recovery, snapshot-based restore,
    and automatic recovery strategies.
    """

    def __init__(
        self, context: Optional[DiscoveryContext] = None
    ) -> None:
        self._lock = threading.RLock()
        self._context = context or DiscoveryContext()
        self._strategies: Dict[str, RecoveryStrategy] = {}
        self._recovery_history: List[Dict[str, Any]] = []
        self._recovery_count = 0
        self._last_recovery: Optional[Dict[str, Any]] = None
        self._max_history = 100
        self._register_default_strategies()

    def _register_default_strategies(self) -> None:
        self._strategies["snapshot_restore"] = SnapshotRestoreStrategy()
        self._strategies["registry_restart"] = RegistryRestartStrategy()
        self._strategies["full_resync"] = FullResyncStrategy()

    def add_strategy(self, strategy: RecoveryStrategy) -> None:
        with self._lock:
            self._strategies[strategy.name] = strategy
        logger.info(
            "Recovery strategy '%s' registered.", strategy.name
        )

    async def execute_recovery(
        self,
        strategy_names: Optional[List[str]] = None,
        error_description: str = "",
    ) -> Dict[str, Any]:
        """Execute recovery strategies.

        Args:
            strategy_names: Specific strategies to run, or
                None for all registered.
            error_description: Description of the error to
                recover from.

        Returns:
            Recovery result.
        """
        with self._lock:
            self._recovery_count += 1

        strategies_to_run: List[RecoveryStrategy] = []
        if strategy_names:
            for name in strategy_names:
                strat = self._strategies.get(name)
                if strat:
                    strategies_to_run.append(strat)
        else:
            strategies_to_run = list(self._strategies.values())

        results: Dict[str, Any] = {}
        recovered = False

        for strategy in strategies_to_run:
            try:
                result = await strategy.execute(self._context)
                results[strategy.name] = result
                if result.get("success", False):
                    strategy.success_count += 1
                    recovered = True
                    logger.info(
                        "Recovery strategy '%s' succeeded.",
                        strategy.name,
                    )
                    break
                else:
                    strategy.failure_count += 1
            except Exception as exc:
                strategy.failure_count += 1
                results[strategy.name] = {
                    "success": False,
                    "error": str(exc),
                }
                logger.warning(
                    "Recovery strategy '%s' failed: %s",
                    strategy.name,
                    exc,
                )

        recovery_result: Dict[str, Any] = {
            "recovered": recovered,
            "error_description": error_description,
            "strategies_run": list(results.keys()),
            "results": results,
            "timestamp": datetime.utcnow().isoformat(),
        }

        with self._lock:
            self._recovery_history.append(recovery_result)
            if len(self._recovery_history) > self._max_history:
                self._recovery_history = (
                    self._recovery_history[-self._max_history:]
                )
            self._last_recovery = recovery_result

        return recovery_result

    def get_strategies(self) -> List[str]:
        with self._lock:
            return sorted(self._strategies.keys())

    def get_history(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._recovery_history)

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "recovery_count": self._recovery_count,
                "strategy_count": len(self._strategies),
                "strategies": {
                    name: {
                        "success_count": strat.success_count,
                        "failure_count": strat.failure_count,
                    }
                    for name, strat in self._strategies.items()
                },
                "last_recovery": self._last_recovery,
                "history_size": len(self._recovery_history),
            }

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"PlatformRecovery(strategies={len(self._strategies)}, "
                f"recoveries={self._recovery_count})"
            )


class SnapshotRestoreStrategy(RecoveryStrategy):
    """Restore from the latest snapshot."""

    def __init__(self) -> None:
        super().__init__("snapshot_restore")

    async def execute(
        self, context: DiscoveryContext
    ) -> Dict[str, Any]:
        snapshot_api = context.get("snapshot_api")
        if snapshot_api is None:
            return {"success": False, "error": "No snapshot API"}

        try:
            get_fn = getattr(snapshot_api, "get_latest", None)
            if callable(get_fn):
                snapshot = get_fn()
                if snapshot is None:
                    return {
                        "success": False,
                        "error": "No snapshot available",
                    }
                restore_fn = getattr(
                    snapshot_api, "restore", None
                )
                if callable(restore_fn):
                    coro = restore_fn(snapshot)
                    if asyncio.iscoroutine(coro):
                        return await coro
                    return coro
        except Exception as exc:
            return {"success": False, "error": str(exc)}

        return {"success": False, "error": "Restore failed"}


class RegistryRestartStrategy(RecoveryStrategy):
    """Attempt to restart the registry."""

    def __init__(self) -> None:
        super().__init__("registry_restart")

    async def execute(
        self, context: DiscoveryContext
    ) -> Dict[str, Any]:
        registry = context.get("registry")
        if registry is None:
            return {"success": False, "error": "No registry"}

        try:
            restart_fn = getattr(registry, "restart", None)
            if callable(restart_fn):
                coro = restart_fn()
                if asyncio.iscoroutine(coro):
                    return await coro
                return coro

            is_ready_fn = getattr(registry, "is_ready", None)
            if callable(is_ready_fn):
                result = is_ready_fn()
                ready = result if not hasattr(result, "__await__") else True
                return {"success": bool(ready)}

            return {"success": True}
        except Exception as exc:
            return {"success": False, "error": str(exc)}


class FullResyncStrategy(RecoveryStrategy):
    """Force full resynchronization of all state."""

    def __init__(self) -> None:
        super().__init__("full_resync")

    async def execute(
        self, context: DiscoveryContext
    ) -> Dict[str, Any]:
        synchronizer = context.get("synchronizer")
        if synchronizer is None:
            return {"success": False, "error": "No synchronizer"}

        try:
            sync_fn = getattr(synchronizer, "sync_full", None)
            if callable(sync_fn):
                coro = sync_fn()
                if asyncio.iscoroutine(coro):
                    return await coro
                return coro
        except Exception as exc:
            return {"success": False, "error": str(exc)}

        return {"success": False, "error": "Sync failed"}
