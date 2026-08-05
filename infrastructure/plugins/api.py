from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .service import PluginService
from .monitoring import PluginMonitoring
from .protection import PluginProtection
from .telemetry import PluginTelemetry
from .events import PluginEventBus

logger = logging.getLogger(__name__)


class PluginAPI:
    """Public REST-like API layer for the plugin platform.

    Provides a unified interface for external consumers (OMS,
    Risk Engine, Execution Engine, etc.) to interact with
    the plugin platform without direct dependency on internal
    classes.

    Usage::

        api = PluginAPI()
        health = await api.health_check()
        plugins = await api.list_plugins()
        await api.start_plugin("my_plugin")
    """

    def __init__(
        self,
        service: Optional[PluginService] = None,
        monitoring: Optional[PluginMonitoring] = None,
        protection: Optional[PluginProtection] = None,
        telemetry: Optional[PluginTelemetry] = None,
        event_bus: Optional[PluginEventBus] = None,
    ) -> None:
        self._service = service or PluginService()
        self._monitoring = monitoring or PluginMonitoring()
        self._protection = protection or PluginProtection()
        self._telemetry = telemetry or PluginTelemetry()
        self._event_bus = event_bus or PluginEventBus()
        self._request_count: int = 0
        self._error_count: int = 0
        self._methods: Dict[str, int] = {}

    async def health_check(self) -> Dict[str, Any]:
        """Run a system health check.

        Returns:
            Dictionary with health status of all sub-systems.
        """
        self._track_request("health_check")
        try:
            service_health = await self._service.health_check()
            monitoring_stats = self._monitoring.get_stats()
            protection_stats = self._protection.get_stats()
            telemetry_stats = self._telemetry.get_stats()

            overall = "healthy"
            issues: List[str] = []

            if protection_stats.get("open_circuits"):
                overall = "degraded"
                issues.append(
                    f"{len(protection_stats['open_circuits'])} open circuits"
                )

            if protection_stats.get("safe_mode"):
                overall = "degraded"
                issues.append("safe mode active")

            return {
                "status": overall,
                "issues": issues,
                "timestamp": self._telemetry._events[-1]["timestamp"]
                if self._telemetry._events
                else 0.0,
                "service": service_health,
                "monitoring": monitoring_stats,
                "protection": protection_stats,
                "telemetry": telemetry_stats,
            }
        except Exception as e:
            self._error_count += 1
            logger.error("Health check failed: %s", e)
            return {
                "status": "unhealthy",
                "issues": [str(e)],
                "error": str(e),
            }

    async def list_plugins(self) -> List[Dict[str, Any]]:
        """List all registered plugins.

        Returns:
            List of plugin data dictionaries.
        """
        self._track_request("list_plugins")
        try:
            plugins = self._service.list_plugins()
            return [
                p.to_dict() if hasattr(p, "to_dict") else {"id": str(p)}
                for p in plugins
            ]
        except Exception as e:
            self._error_count += 1
            logger.error("List plugins failed: %s", e)
            return []

    async def get_plugin(self, plugin_id: str) -> Dict[str, Any]:
        """Get detailed information for a specific plugin.

        Args:
            plugin_id: The plugin identifier.

        Returns:
            Plugin data dictionary, or error dict if not found.
        """
        self._track_request("get_plugin")
        try:
            plugin = self._service.get_plugin(plugin_id)
            if plugin is None:
                self._telemetry.record_event(
                    "get_plugin_not_found", plugin_id
                )
                return {
                    "error": "not_found",
                    "plugin_id": plugin_id,
                }
            data = plugin.to_dict() if hasattr(plugin, "to_dict") else {"id": str(plugin)}
            self._telemetry.record_event("get_plugin", plugin_id, data)
            return data
        except Exception as e:
            self._error_count += 1
            logger.error("Get plugin '%s' failed: %s", plugin_id, e)
            return {"error": str(e), "plugin_id": plugin_id}

    async def install_plugin(
        self, plugin_id: str, version: Optional[str] = None
    ) -> Dict[str, Any]:
        """Install a plugin from the marketplace.

        Args:
            plugin_id: The plugin identifier to install.
            version: Optional target version.

        Returns:
            Installation result dictionary.
        """
        self._track_request("install_plugin")
        span_id = self._telemetry.start_span(
            "install_plugin", plugin_id=plugin_id
        )
        try:
            protection_result = await self._protection.check_plugin(plugin_id)
            if not protection_result.get("allowed"):
                self._telemetry.end_span(span_id, status="blocked")
                return {
                    "success": False,
                    "error": "blocked",
                    "reason": protection_result.get("reason", ""),
                    "plugin_id": plugin_id,
                }

            result = await self._service.manager.install(
                self._service.manager._marketplace.install_plugin(
                    plugin_id, version
                )
            )
            self._telemetry.record_event(
                "installed", plugin_id, {"version": version or "latest"}
            )
            self._telemetry.end_span(span_id, status="ok")
            return {
                "success": True,
                "plugin_id": plugin_id,
                "result": str(result),
            }
        except Exception as e:
            self._error_count += 1
            self._telemetry.end_span(span_id, status="error")
            logger.error(
                "Install plugin '%s' failed: %s", plugin_id, e
            )
            return {
                "success": False,
                "error": str(e),
                "plugin_id": plugin_id,
            }

    async def update_plugin(
        self, plugin_id: str, version: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update an installed plugin to a newer version.

        Args:
            plugin_id: The plugin identifier to update.
            version: Optional target version.

        Returns:
            Update result dictionary.
        """
        self._track_request("update_plugin")
        span_id = self._telemetry.start_span(
            "update_plugin", plugin_id=plugin_id
        )
        try:
            result = await self._service.manager._marketplace.update_plugin(
                plugin_id, version
            )
            self._telemetry.record_event(
                "updated", plugin_id, {"version": version or "latest"}
            )
            self._telemetry.end_span(span_id, status="ok")
            return {
                "success": True,
                "plugin_id": plugin_id,
                "result": str(result),
            }
        except Exception as e:
            self._error_count += 1
            self._telemetry.end_span(span_id, status="error")
            logger.error(
                "Update plugin '%s' failed: %s", plugin_id, e
            )
            return {
                "success": False,
                "error": str(e),
                "plugin_id": plugin_id,
            }

    async def uninstall_plugin(self, plugin_id: str) -> Dict[str, Any]:
        """Uninstall a plugin completely.

        Args:
            plugin_id: The plugin identifier to uninstall.

        Returns:
            Uninstall result dictionary.
        """
        self._track_request("uninstall_plugin")
        span_id = self._telemetry.start_span(
            "uninstall_plugin", plugin_id=plugin_id
        )
        try:
            result = await self._service.remove(plugin_id)
            self._telemetry.record_event("uninstalled", plugin_id)
            self._telemetry.end_span(span_id, status="ok")
            return {
                "success": True,
                "plugin_id": plugin_id,
                "result": result,
            }
        except Exception as e:
            self._error_count += 1
            self._telemetry.end_span(span_id, status="error")
            logger.error(
                "Uninstall plugin '%s' failed: %s", plugin_id, e
            )
            return {
                "success": False,
                "error": str(e),
                "plugin_id": plugin_id,
            }

    async def start_plugin(self, plugin_id: str) -> Dict[str, Any]:
        """Start a plugin.

        Args:
            plugin_id: The plugin identifier to start.

        Returns:
            Start result dictionary.
        """
        self._track_request("start_plugin")
        span_id = self._telemetry.start_span(
            "start_plugin", plugin_id=plugin_id
        )
        try:
            protection_result = await self._protection.check_plugin(plugin_id)
            if not protection_result.get("allowed"):
                self._telemetry.end_span(span_id, status="blocked")
                return {
                    "success": False,
                    "error": "blocked",
                    "reason": protection_result.get("reason", ""),
                    "plugin_id": plugin_id,
                }

            result = await self._service.start_plugin(plugin_id)
            self._telemetry.record_event("started", plugin_id, result)
            self._telemetry.end_span(span_id, status="ok")
            self._protection.increment_restart(plugin_id)
            return {
                "success": True,
                "plugin_id": plugin_id,
                "result": result,
            }
        except Exception as e:
            self._error_count += 1
            self._telemetry.end_span(span_id, status="error")
            await self._protection.on_failure(plugin_id, str(e))
            logger.error(
                "Start plugin '%s' failed: %s", plugin_id, e
            )
            return {
                "success": False,
                "error": str(e),
                "plugin_id": plugin_id,
            }

    async def stop_plugin(self, plugin_id: str) -> Dict[str, Any]:
        """Stop a running plugin.

        Args:
            plugin_id: The plugin identifier to stop.

        Returns:
            Stop result dictionary.
        """
        self._track_request("stop_plugin")
        span_id = self._telemetry.start_span(
            "stop_plugin", plugin_id=plugin_id
        )
        try:
            result = await self._service.stop_plugin(plugin_id)
            self._telemetry.record_event("stopped", plugin_id, result)
            self._telemetry.end_span(span_id, status="ok")
            return {
                "success": True,
                "plugin_id": plugin_id,
                "result": result,
            }
        except Exception as e:
            self._error_count += 1
            self._telemetry.end_span(span_id, status="error")
            logger.error(
                "Stop plugin '%s' failed: %s", plugin_id, e
            )
            return {
                "success": False,
                "error": str(e),
                "plugin_id": plugin_id,
            }

    async def reload_plugin(self, plugin_id: str) -> Dict[str, Any]:
        """Reload a plugin.

        Args:
            plugin_id: The plugin identifier to reload.

        Returns:
            Reload result dictionary.
        """
        self._track_request("reload_plugin")
        span_id = self._telemetry.start_span(
            "reload_plugin", plugin_id=plugin_id
        )
        try:
            protection_result = await self._protection.check_plugin(plugin_id)
            if not protection_result.get("allowed"):
                self._telemetry.end_span(span_id, status="blocked")
                return {
                    "success": False,
                    "error": "blocked",
                    "reason": protection_result.get("reason", ""),
                    "plugin_id": plugin_id,
                }

            result = await self._service.reload_plugin(plugin_id)
            self._telemetry.record_event("reloaded", plugin_id, result)
            self._telemetry.end_span(span_id, status="ok")
            self._protection.increment_restart(plugin_id)
            self._monitoring.increment_restart()
            return {
                "success": True,
                "plugin_id": plugin_id,
                "result": result,
            }
        except Exception as e:
            self._error_count += 1
            self._telemetry.end_span(span_id, status="error")
            await self._protection.on_failure(plugin_id, str(e))
            logger.error(
                "Reload plugin '%s' failed: %s", plugin_id, e
            )
            return {
                "success": False,
                "error": str(e),
                "plugin_id": plugin_id,
            }

    async def search_plugins(self, query: str) -> List[Dict[str, Any]]:
        """Search for plugins matching a query string.

        Args:
            query: The search query.

        Returns:
            List of matching plugin data dictionaries.
        """
        self._track_request("search_plugins")
        try:
            all_plugins = await self.list_plugins()
            query_lower = query.lower()
            results: List[Dict[str, Any]] = []
            for p in all_plugins:
                searchable = " ".join(
                    str(p.get(k, ""))
                    for k in ("id", "name", "description", "author", "version")
                ).lower()
                if query_lower in searchable:
                    results.append(p)
            return results
        except Exception as e:
            self._error_count += 1
            logger.error("Search plugins failed: %s", e)
            return []

    async def get_snapshot(self) -> Dict[str, Any]:
        """Get a comprehensive system snapshot.

        Returns:
            Dictionary with state from all sub-systems.
        """
        self._track_request("get_snapshot")
        try:
            monitoring_metrics = await self._monitoring.collect_metrics()
            return {
                "monitoring": monitoring_metrics,
                "protection": self._protection.get_stats(),
                "telemetry": self._telemetry.get_stats(),
                "services": self._service.get_stats(),
                "event_bus": self._event_bus.get_stats(),
            }
        except Exception as e:
            self._error_count += 1
            logger.error("Get snapshot failed: %s", e)
            return {"error": str(e)}

    def _track_request(self, method: str) -> None:
        """Track an API request for statistics.

        Args:
            method: The method name being invoked.
        """
        self._request_count += 1
        self._methods[method] = self._methods.get(method, 0) + 1

    def get_stats(self) -> Dict[str, Any]:
        """Get API layer statistics.

        Returns:
            Dictionary with request counts, error counts,
            and per-method breakdowns.
        """
        return {
            "total_requests": self._request_count,
            "total_errors": self._error_count,
            "methods": dict(self._methods),
            "monitoring": self._monitoring.get_stats(),
            "protection": self._protection.get_stats(),
            "telemetry": self._telemetry.get_stats(),
        }