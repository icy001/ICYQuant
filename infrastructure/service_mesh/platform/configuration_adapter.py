"""Configuration Platform Adapter for the Service Mesh Platform.

Provides ``ConfigurationPlatformAdapter`` for integrating the
Configuration Platform with the mesh for policy sync and
runtime refresh.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .telemetry import PlatformTelemetry
from .metrics import PlatformMetrics

logger = logging.getLogger(__name__)


class ConfigurationPlatformAdapter:
    """Adapter for integrating Configuration Platform with the mesh."""

    def __init__(
        self,
        telemetry: Optional[PlatformTelemetry] = None,
        metrics: Optional[PlatformMetrics] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._telemetry = telemetry or PlatformTelemetry()
        self._metrics = metrics or PlatformMetrics()
        self._config: Dict[str, Any] = {}
        self._config_history: List[Dict[str, Any]] = []
        self._max_history = 500
        self._config_count = 0
        self._change_handlers: Dict[str, Callable] = {}
        self._adapter_active = False

    async def initialize(
        self, config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Initialize the configuration adapter."""
        if config:
            self._config = config
        self._adapter_active = True
        self._telemetry.log_platform_event(
            "config_adapter_initialized", "configuration",
        )
        logger.info("Configuration adapter initialized.")
        return {"success": True}

    async def shutdown(self) -> Dict[str, Any]:
        self._adapter_active = False
        self._telemetry.log_platform_event(
            "config_adapter_shutdown", "configuration",
        )
        return {"success": True}

    @property
    def is_active(self) -> bool:
        return self._adapter_active

    def register_change_handler(
        self,
        config_key: str,
        handler: Callable,
    ) -> None:
        self._change_handlers[config_key] = handler

    async def update_config(
        self,
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update mesh configuration."""
        self._config_count += 1

        with self._lock:
            old_config = dict(self._config)
            self._config.update(config)

        # Add to history
        self._config_history.append({
            "updated_at": datetime.utcnow().isoformat(),
            "old_keys": list(old_config.keys()),
            "new_keys": list(config.keys()),
            "config_keys": list(self._config.keys()),
        })
        if len(self._config_history) > self._max_history:
            self._config_history = (
                self._config_history[-self._max_history:]
            )

        # Fire change handlers
        changed_keys = set(config.keys())
        for key in changed_keys:
            handler = self._change_handlers.get(key)
            if handler:
                try:
                    result = handler(self._config)
                    if asyncio.iscoroutine(result):
                        result = await result
                except Exception as exc:
                    self._telemetry.log_error(
                        "config_adapter",
                        "change_handler_failed",
                        str(exc),
                        {"key": key},
                    )

        self._metrics.increment_counter(
            "icyquant_mesh_config_updates_total",
        )
        self._telemetry.log_platform_event(
            "config_updated", "configuration",
            {"updated_keys": list(changed_keys)},
        )
        logger.info(
            "Configuration updated (keys=%d).", len(changed_keys)
        )
        return {
            "success": True,
            "config_count": self._config_count,
            "updated_keys": list(changed_keys),
        }

    async def refresh_runtime(
        self, config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Refresh runtime configuration."""
        if config:
            await self.update_config(config)

        self._telemetry.log_platform_event(
            "runtime_refreshed", "configuration",
        )
        return {"success": True, "refreshed": True}

    def get_config(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._config)

    def get_config_value(
        self, key: str, default: Any = None
    ) -> Any:
        return self._config.get(key, default)

    def get_history(
        self, limit: int = 50
    ) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._config_history[-limit:])

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "active": self._adapter_active,
                "config_count": self._config_count,
                "config_keys": list(self._config.keys()),
                "history_size": len(self._config_history),
                "change_handlers": list(
                    self._change_handlers.keys()
                ),
            }

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"ConfigurationPlatformAdapter("
                f"config_keys={len(self._config)}, "
                f"active={self._adapter_active})"
            )
