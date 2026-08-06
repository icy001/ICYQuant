"""Mesh Plugin SDK for the Service Mesh Platform.

Provides ``MeshPlugin`` base class and ``MeshPluginContext``
for developing mesh platform plugins that extend traffic,
security, policy, telemetry, and custom middleware.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .telemetry import PlatformTelemetry
from .metrics import PlatformMetrics

logger = logging.getLogger(__name__)


class PluginCategory(str, Enum):
    """Category of mesh plugin."""

    TRAFFIC = "traffic"
    SECURITY = "security"
    POLICY = "policy"
    TELEMETRY = "telemetry"
    CUSTOM = "custom"


class MeshPluginContext:
    """Context passed to mesh plugin during execution."""

    def __init__(
        self,
        plugin_name: str,
        telemetry: Optional[PlatformTelemetry] = None,
        metrics: Optional[PlatformMetrics] = None,
    ) -> None:
        self.plugin_name = plugin_name
        self.telemetry = telemetry or PlatformTelemetry()
        self.metrics = metrics or PlatformMetrics()
        self._data: Dict[str, Any] = {}
        self._headers: Dict[str, str] = {}
        self._metadata: Dict[str, Any] = {}

    @property
    def data(self) -> Dict[str, Any]:
        return self._data

    @property
    def headers(self) -> Dict[str, str]:
        return self._headers

    @property
    def metadata(self) -> Dict[str, Any]:
        return self._metadata

    def set_data(self, key: str, value: Any) -> None:
        self._data[key] = value

    def get_data(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set_header(self, key: str, value: str) -> None:
        self._headers[key] = value

    def set_metadata(self, key: str, value: Any) -> None:
        self._metadata[key] = value

    def log_event(
        self, event_type: str, details: Optional[Dict[str, Any]] = None
    ) -> None:
        self.telemetry.log_plugin(
            self.plugin_name, event_type, details
        )

    def increment_metric(
        self,
        name: str,
        value: int = 1,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        self.metrics.increment_counter(name, value, labels)


class MeshPlugin:
    """Base class for mesh platform plugins.

    Subclass this to create custom plugins that extend mesh
    platform capabilities. Override the lifecycle methods:
    initialize, on_request, on_response, and shutdown.
    """

    name: str = "base_plugin"
    version: str = "1.0.0"
    category: PluginCategory = PluginCategory.CUSTOM
    description: str = "Base mesh plugin"

    def __init__(self) -> None:
        self._context: Optional[MeshPluginContext] = None
        self._initialized = False
        self._request_count = 0
        self._response_count = 0
        self._error_count = 0
        self._started_at: Optional[float] = None

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    async def initialize(
        self,
        context: Optional[MeshPluginContext] = None,
    ) -> Dict[str, Any]:
        """Initialize the plugin. Override in subclasses."""
        self._context = context or MeshPluginContext(self.name)
        self._initialized = True
        self._started_at = time.monotonic()
        self._context.log_event("plugin_initialized")
        logger.info(
            "Plugin '%s' v%s initialized.", self.name, self.version
        )
        return {"success": True, "plugin": self.name}

    async def on_request(
        self,
        request: Dict[str, Any],
        context: Optional[MeshPluginContext] = None,
    ) -> Dict[str, Any]:
        """Process an incoming request. Override in subclasses."""
        self._request_count += 1
        ctx = context or self._context
        if ctx:
            ctx.log_event("on_request", {"count": self._request_count})
        return {"success": True, "request": request}

    async def on_response(
        self,
        response: Dict[str, Any],
        context: Optional[MeshPluginContext] = None,
    ) -> Dict[str, Any]:
        """Process an outgoing response. Override in subclasses."""
        self._response_count += 1
        ctx = context or self._context
        if ctx:
            ctx.log_event("on_response", {"count": self._response_count})
        return {"success": True, "response": response}

    async def shutdown(
        self,
        context: Optional[MeshPluginContext] = None,
    ) -> Dict[str, Any]:
        """Shutdown the plugin. Override in subclasses."""
        self._initialized = False
        ctx = context or self._context
        if ctx:
            ctx.log_event("plugin_shutdown")
        logger.info("Plugin '%s' shut down.", self.name)
        return {"success": True, "plugin": self.name}

    def on_error(
        self,
        error: Exception,
        context: Optional[MeshPluginContext] = None,
    ) -> None:
        """Handle an error during plugin execution."""
        self._error_count += 1
        ctx = context or self._context
        if ctx:
            ctx.telemetry.log_error(
                "plugin",
                "plugin_error",
                str(error),
                {"plugin": self.name},
            )
        logger.error(
            "Plugin '%s' error: %s", self.name, error
        )

    def get_context(self) -> Optional[MeshPluginContext]:
        return self._context

    def get_stats(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "category": self.category.value,
            "initialized": self._initialized,
            "request_count": self._request_count,
            "response_count": self._response_count,
            "error_count": self._error_count,
            "uptime_s": (
                time.monotonic() - self._started_at
                if self._started_at
                else 0
            ),
        }

    def __repr__(self) -> str:
        return (
            f"MeshPlugin(name={self.name}, "
            f"version={self.version}, "
            f"initialized={self._initialized})"
        )


class TrafficPlugin(MeshPlugin):
    """Plugin for traffic management extensions."""

    category = PluginCategory.TRAFFIC

    async def on_request(
        self,
        request: Dict[str, Any],
        context: Optional[MeshPluginContext] = None,
    ) -> Dict[str, Any]:
        result = await super().on_request(request, context)
        ctx = context or self._context
        if ctx:
            ctx.set_data("traffic_processed", True)
        return result


class SecurityPlugin(MeshPlugin):
    """Plugin for security extensions."""

    category = PluginCategory.SECURITY

    async def on_request(
        self,
        request: Dict[str, Any],
        context: Optional[MeshPluginContext] = None,
    ) -> Dict[str, Any]:
        result = await super().on_request(request, context)
        ctx = context or self._context
        if ctx:
            ctx.set_data("security_verified", True)
        return result


class PolicyPlugin(MeshPlugin):
    """Plugin for policy enforcement extensions."""

    category = PluginCategory.POLICY

    async def on_request(
        self,
        request: Dict[str, Any],
        context: Optional[MeshPluginContext] = None,
    ) -> Dict[str, Any]:
        result = await super().on_request(request, context)
        ctx = context or self._context
        if ctx:
            ctx.set_data("policy_evaluated", True)
        return result


class TelemetryPlugin(MeshPlugin):
    """Plugin for telemetry extensions."""

    category = PluginCategory.TELEMETRY

    async def on_response(
        self,
        response: Dict[str, Any],
        context: Optional[MeshPluginContext] = None,
    ) -> Dict[str, Any]:
        result = await super().on_response(response, context)
        ctx = context or self._context
        if ctx:
            ctx.set_data("telemetry_recorded", True)
        return result
