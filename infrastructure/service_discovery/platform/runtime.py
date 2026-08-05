"""Service discovery runtime for ICYQuant platform.

Provides ``DiscoveryRuntime`` for starting, stopping, reloading,
and dynamically configuring the service discovery platform.
Supports hot reload, dynamic configuration, automatic recovery,
and runtime diagnostics.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .runtime_context import DiscoveryContext
from .monitoring import PlatformMetrics

logger = logging.getLogger(__name__)


class DiscoveryRuntime:
    """Runtime management for the service discovery platform.

    Provides start/stop/reload lifecycle, hot reload support,
    dynamic configuration updates, automatic recovery on
    failure, and runtime diagnostics.

    Args:
        context: Optional ``DiscoveryContext`` instance.
        metrics: Optional ``PlatformMetrics`` instance.
    """

    def __init__(
        self,
        context: Optional[DiscoveryContext] = None,
        metrics: Optional[PlatformMetrics] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._context = context or DiscoveryContext()
        self._metrics = metrics or PlatformMetrics()
        self._running = False
        self._start_count = 0
        self._stop_count = 0
        self._reload_count = 0
        self._config: Dict[str, Any] = {}
        self._start_time: Optional[datetime] = None
        self._last_reload_time: Optional[datetime] = None
        self._reload_handlers: Dict[str, Callable] = {}
        self._recovery_strategies: List[Callable] = []
        self._diagnostics: Dict[str, Any] = {
            "reload_count": 0,
            "last_reload": None,
            "reload_history": [],
        }

    async def start(
        self, config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Start the discovery runtime.

        Args:
            config: Optional configuration dictionary.

        Returns:
            Start result dictionary.
        """
        with self._lock:
            self._start_count += 1
            self._running = True
            if config:
                self._config = dict(config)
            self._start_time = datetime.utcnow()

        self._metrics.record_runtime("start", duration=0.0)

        result: Dict[str, Any] = {
            "started": True,
            "config": self._config,
            "timestamp": self._start_time.isoformat(),
            "component_count": len(self._context.list_components()),
        }
        logger.info(
            "Discovery runtime started with %d components.",
            result["component_count"],
        )
        return result

    async def stop(self) -> Dict[str, Any]:
        """Stop the discovery runtime.

        Returns:
            Stop result dictionary.
        """
        with self._lock:
            self._stop_count += 1
            self._running = False

        self._metrics.record_runtime("stop", duration=0.0)

        result: Dict[str, Any] = {
            "stopped": True,
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_s": self._get_uptime(),
        }
        logger.info("Discovery runtime stopped.")
        return result

    async def reload(
        self, config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Hot reload the runtime configuration.

        Calls registered reload handlers and updates the
        configuration atomically.

        Args:
            config: New configuration to apply.

        Returns:
            Reload result dictionary.
        """
        start = time.monotonic()

        with self._lock:
            self._reload_count += 1
            if config:
                self._config = dict(config)
            self._last_reload_time = datetime.utcnow()

        reload_results: Dict[str, Any] = {}
        for name, handler in self._reload_handlers.items():
            try:
                coro = handler(self._config)
                if asyncio.iscoroutine(coro):
                    outcome = await coro
                else:
                    outcome = coro
                reload_results[name] = {
                    "success": True,
                    "outcome": str(outcome)[:200] if outcome else None,
                }
            except Exception as exc:
                reload_results[name] = {
                    "success": False,
                    "error": str(exc),
                }
                logger.warning(
                    "Reload handler '%s' failed: %s", name, exc
                )

        duration = time.monotonic() - start
        self._metrics.record_reload(
            "runtime",
            all(
                r.get("success", False)
                for r in reload_results.values()
            ),
            duration=duration,
        )

        self._diagnostics["reload_count"] += 1
        self._diagnostics["last_reload"] = (
            datetime.utcnow().isoformat()
        )
        self._diagnostics["reload_history"].append(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "duration_s": duration,
                "handlers": reload_results,
            }
        )
        if len(self._diagnostics["reload_history"]) > 100:
            self._diagnostics["reload_history"] = (
                self._diagnostics["reload_history"][-100:]
            )

        result: Dict[str, Any] = {
            "reloaded": True,
            "config": self._config,
            "handlers": reload_results,
            "duration_s": duration,
            "timestamp": datetime.utcnow().isoformat(),
        }
        logger.info(
            "Runtime reloaded in %.3fs (%d handlers).",
            duration,
            len(reload_results),
        )
        return result

    def register_reload_handler(
        self, name: str, handler: Callable
    ) -> None:
        """Register a handler for reload events.

        Args:
            name: Handler name.
            handler: Callable accepting the config dict.
        """
        with self._lock:
            self._reload_handlers[name] = handler

    def add_recovery_strategy(
        self, strategy: Callable
    ) -> None:
        """Add an automatic recovery strategy.

        Args:
            strategy: Callable that attempts recovery.
        """
        with self._lock:
            self._recovery_strategies.append(strategy)

    async def attempt_recovery(
        self, error: Optional[str] = None
    ) -> Dict[str, Any]:
        """Attempt automatic recovery using registered strategies.

        Args:
            error: Description of the error to recover from.

        Returns:
            Recovery result dictionary.
        """
        for strategy in self._recovery_strategies:
            try:
                coro = strategy(error)
                if asyncio.iscoroutine(coro):
                    result = await coro
                else:
                    result = coro
                if result:
                    return {
                        "recovered": True,
                        "strategy": strategy.__name__,
                        "result": str(result)[:200],
                    }
            except Exception:
                continue

        return {
            "recovered": False,
            "error": error,
            "strategy_count": len(self._recovery_strategies),
        }

    def get_diagnostics(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._diagnostics)

    def _get_uptime(self) -> float:
        if self._start_time is None:
            return 0.0
        return (datetime.utcnow() - self._start_time).total_seconds()

    def is_running(self) -> bool:
        with self._lock:
            return self._running

    def get_context(self) -> DiscoveryContext:
        return self._context

    def get_metrics(self) -> PlatformMetrics:
        return self._metrics

    def get_config(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._config)

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "running": self._running,
                "start_count": self._start_count,
                "stop_count": self._stop_count,
                "reload_count": self._reload_count,
                "uptime_s": self._get_uptime(),
                "reload_handlers": sorted(
                    self._reload_handlers.keys()
                ),
                "recovery_strategies": len(
                    self._recovery_strategies
                ),
                "config_keys": sorted(self._config.keys()),
                "last_reload": (
                    self._last_reload_time.isoformat()
                    if self._last_reload_time
                    else None
                ),
            }

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"DiscoveryRuntime(running={self._running}, "
                f"reloads={self._reload_count})"
            )
