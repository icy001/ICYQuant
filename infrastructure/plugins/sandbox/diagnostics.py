"""Sandbox diagnostics.

Provides :class:`SandboxDiagnostics` for collecting and
reporting diagnostic information about sandboxed plugin
executions, including performance data and error analysis.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SandboxDiagnostics:
    """Collects and reports sandbox diagnostic information.

    Gathers diagnostic data for sandboxed plugins including
    execution time, resource usage, error traces, and
    performance metrics.

    Attributes:
        _diagnostics: Map of plugin_id → diagnostic data.
        _lock: Thread-safe reentrant lock.
    """

    def __init__(self) -> None:
        self._diagnostics: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()

    def record_execution(
        self,
        plugin_id: str,
        function_name: str,
        duration: float,
        success: bool,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a function execution diagnostic.

        Args:
            plugin_id: The plugin that executed the function.
            function_name: The name of the executed function.
            duration: Execution duration in seconds.
            success: Whether the execution succeeded.
            error: Error message if the execution failed.
            metadata: Optional additional diagnostic metadata.
        """
        with self._lock:
            if plugin_id not in self._diagnostics:
                self._diagnostics[plugin_id] = {
                    "executions": [],
                    "errors": [],
                    "total_executions": 0,
                    "total_errors": 0,
                    "total_duration": 0.0,
                }

            diag = self._diagnostics[plugin_id]
            entry: Dict[str, Any] = {
                "function": function_name,
                "duration": duration,
                "success": success,
                "timestamp": time.time(),
                "metadata": metadata or {},
            }
            if error:
                entry["error"] = error
                diag["errors"].append(entry)
                diag["total_errors"] += 1

            diag["executions"].append(entry)
            diag["total_executions"] += 1
            diag["total_duration"] += duration

            executions = diag["executions"]
            if len(executions) > 100:
                diag["executions"] = executions[-100:]
            errors = diag["errors"]
            if len(errors) > 50:
                diag["errors"] = errors[-50:]

    def get_diagnostics(
        self, plugin_id: str
    ) -> Dict[str, Any]:
        """Get diagnostic data for a plugin.

        Args:
            plugin_id: Unique identifier for the plugin.

        Returns:
            A dictionary with execution history, error history,
            and summary statistics.
        """
        with self._lock:
            diag = self._diagnostics.get(plugin_id, {})
            if not diag:
                return {
                    "plugin_id": plugin_id,
                    "executions": [],
                    "errors": [],
                    "total_executions": 0,
                    "total_errors": 0,
                    "total_duration": 0.0,
                    "avg_duration": 0.0,
                    "success_rate": 0.0,
                }

            total = diag["total_executions"]
            errors = diag["total_errors"]
            dur = diag["total_duration"]
            return {
                "plugin_id": plugin_id,
                "executions": diag["executions"][-20:],
                "errors": diag["errors"][-10:],
                "total_executions": total,
                "total_errors": errors,
                "total_duration": dur,
                "avg_duration": dur / total if total > 0 else 0.0,
                "success_rate": (
                    (total - errors) / total if total > 0 else 0.0
                ),
            }

    def get_error_summary(
        self, plugin_id: str
    ) -> List[Dict[str, Any]]:
        """Get recent errors for a plugin.

        Args:
            plugin_id: Unique identifier for the plugin.

        Returns:
            A list of recent error entries.
        """
        with self._lock:
            diag = self._diagnostics.get(plugin_id, {})
            return list(diag.get("errors", [])[-10:])

    def get_slow_functions(
        self, plugin_id: str, threshold: float = 1.0
    ) -> List[Dict[str, Any]]:
        """Identify slow-executing functions for a plugin.

        Args:
            plugin_id: Unique identifier for the plugin.
            threshold: Duration threshold in seconds.

        Returns:
            A list of execution entries exceeding the threshold,
            sorted by duration descending.
        """
        with self._lock:
            diag = self._diagnostics.get(plugin_id, {})
            slow = [
                e
                for e in diag.get("executions", [])
                if e.get("duration", 0) > threshold
            ]
            return sorted(
                slow, key=lambda e: e["duration"], reverse=True
            )

    def clear_diagnostics(self, plugin_id: str) -> None:
        """Clear diagnostic data for a plugin.

        Args:
            plugin_id: Unique identifier for the plugin.
        """
        with self._lock:
            self._diagnostics.pop(plugin_id, None)
            logger.debug(
                "Cleared diagnostics for plugin %s", plugin_id
            )

    def get_stats(self) -> Dict[str, Any]:
        """Get diagnostics statistics.

        Returns:
            A dictionary with ``total_plugins`` and per-plugin
            summary.
        """
        with self._lock:
            plugins = []
            for pid in self._diagnostics:
                d = self._diagnostics[pid]
                plugins.append({
                    "plugin_id": pid,
                    "total_executions": d.get("total_executions", 0),
                    "total_errors": d.get("total_errors", 0),
                })
            return {
                "total_plugins": len(self._diagnostics),
                "plugins": plugins,
            }