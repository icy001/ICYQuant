"""Sandbox recovery management.

Provides :class:`RecoveryManager` for handling sandbox
failures, performing automatic recovery procedures, and
managing plugin restart strategies.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional

from ..exceptions import PluginSandboxError

logger = logging.getLogger(__name__)


class RecoveryManager:
    """Manages recovery and restart strategies for failed sandboxes.

    Tracks failure counts per plugin and applies configurable
    recovery strategies including exponential backoff,
    circuit-breaking, and automatic restart.

    Attributes:
        _failures: Map of plugin_id → failure metadata.
        _restart_handlers: Map of plugin_id → restart handler.
        _lock: Thread-safe reentrant lock.
        _max_retries: Maximum restart attempts before
            circuit-breaking.
        _backoff_base: Base backoff multiplier in seconds.
    """

    def __init__(
        self,
        max_retries: int = 5,
        backoff_base: float = 1.0,
        circuit_breaker_timeout: float = 60.0,
    ) -> None:
        """Initialize the recovery manager.

        Args:
            max_retries: Maximum restart attempts before
                circuit-breaking.
            backoff_base: Base seconds for exponential backoff.
            circuit_breaker_timeout: Seconds to wait when circuit
                breaker is open before allowing retries.
        """
        self._failures: Dict[str, Dict[str, Any]] = {}
        self._restart_handlers: Dict[
            str, Callable[[], Any]
        ] = {}
        self._lock = threading.RLock()
        self._max_retries = max_retries
        self._backoff_base = backoff_base
        self._circuit_breaker_timeout = circuit_breaker_timeout

    def register_restart_handler(
        self, plugin_id: str, handler: Callable[[], Any]
    ) -> None:
        """Register a restart handler for a plugin.

        Args:
            plugin_id: Unique identifier for the plugin.
            handler: A callable that restarts the plugin's sandbox.
        """
        with self._lock:
            self._restart_handlers[plugin_id] = handler
            logger.debug(
                "Registered restart handler for plugin %s", plugin_id
            )

    def record_failure(
        self,
        plugin_id: str,
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record a sandbox failure for a plugin.

        Args:
            plugin_id: Unique identifier for the plugin.
            error: Description of the failure.

        Returns:
            A dictionary with ``should_retry`` (bool),
            ``backoff_seconds`` (float), and ``circuit_open`` (bool).
        """
        with self._lock:
            if plugin_id not in self._failures:
                self._failures[plugin_id] = {
                    "count": 0,
                    "last_failure": 0.0,
                    "circuit_open": False,
                    "open_until": 0.0,
                    "errors": [],
                }

            failure = self._failures[plugin_id]
            failure["count"] += 1
            failure["last_failure"] = time.time()
            failure["errors"].append(error or "unknown error")

            if len(failure["errors"]) > 50:
                failure["errors"] = failure["errors"][-50:]

            should_retry = failure["count"] <= self._max_retries

            if not should_retry:
                failure["circuit_open"] = True
                failure["open_until"] = (
                    time.time() + self._circuit_breaker_timeout
                )
                logger.warning(
                    "Circuit breaker opened for plugin %s after %d "
                    "failures; cooling down for %.0fs",
                    plugin_id,
                    failure["count"],
                    self._circuit_breaker_timeout,
                )

            backoff = min(
                self._backoff_base * (2 ** (failure["count"] - 1)),
                300.0,
            )

            return {
                "plugin_id": plugin_id,
                "should_retry": should_retry,
                "backoff_seconds": backoff,
                "circuit_open": failure["circuit_open"],
                "failure_count": failure["count"],
            }

    def attempt_recovery(
        self, plugin_id: str
    ) -> Dict[str, Any]:
        """Attempt to recover a failed plugin's sandbox.

        Args:
            plugin_id: Unique identifier for the plugin.

        Returns:
            A dictionary with ``success`` (bool), ``action`` taken,
            and ``details``.

        Raises:
            PluginSandboxError: If no restart handler is registered.
        """
        with self._lock:
            if plugin_id not in self._restart_handlers:
                raise PluginSandboxError(
                    f"No restart handler registered for plugin: "
                    f"{plugin_id}"
                )

            failure = self._failures.get(plugin_id, {})
            if failure.get("circuit_open", False):
                if time.time() < failure.get("open_until", 0):
                    return {
                        "plugin_id": plugin_id,
                        "success": False,
                        "action": "circuit_breaker_open",
                        "message": "Circuit breaker is open; "
                        "cannot attempt recovery yet",
                    }
                else:
                    failure["circuit_open"] = False
                    logger.info(
                        "Circuit breaker closed for plugin %s",
                        plugin_id,
                    )

            handler = self._restart_handlers[plugin_id]

        try:
            handler()
            self._reset_failures(plugin_id)
            logger.info(
                "Recovery successful for plugin %s", plugin_id
            )
            return {
                "plugin_id": plugin_id,
                "success": True,
                "action": "restarted",
            }
        except Exception as exc:
            logger.error(
                "Recovery failed for plugin %s: %s", plugin_id, exc
            )
            result = self.record_failure(plugin_id, str(exc))
            return {
                "plugin_id": plugin_id,
                "success": False,
                "action": "recovery_failed",
                "error": str(exc),
                "should_retry": result["should_retry"],
            }

    def _reset_failures(self, plugin_id: str) -> None:
        """Reset failure tracking for a plugin (must be called
        with lock or after lock release for the update).

        Args:
            plugin_id: Unique identifier for the plugin.
        """
        with self._lock:
            if plugin_id in self._failures:
                self._failures[plugin_id]["count"] = 0
                self._failures[plugin_id]["circuit_open"] = False
                self._failures[plugin_id]["errors"] = []

    def get_failure_info(
        self, plugin_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get failure information for a plugin.

        Args:
            plugin_id: Unique identifier for the plugin.

        Returns:
            A failure info dictionary or None if no failures
            recorded.
        """
        with self._lock:
            failure = self._failures.get(plugin_id)
            if failure is None:
                return None
            return dict(failure)

    def reset_plugin(self, plugin_id: str) -> None:
        """Reset failure tracking for a plugin.

        Args:
            plugin_id: Unique identifier for the plugin.
        """
        self._reset_failures(plugin_id)

    def get_stats(self) -> Dict[str, Any]:
        """Get recovery manager statistics.

        Returns:
            A dictionary with failure counts and circuit breaker
            status per plugin.
        """
        with self._lock:
            plugins = []
            for pid, failure in self._failures.items():
                plugins.append({
                    "plugin_id": pid,
                    "failure_count": failure.get("count", 0),
                    "circuit_open": failure.get("circuit_open", False),
                    "last_failure": failure.get("last_failure", 0),
                })
            return {
                "total_failed_plugins": len(self._failures),
                "circuits_open": sum(
                    1
                    for f in self._failures.values()
                    if f.get("circuit_open", False)
                ),
                "plugins": plugins,
                "max_retries": self._max_retries,
            }