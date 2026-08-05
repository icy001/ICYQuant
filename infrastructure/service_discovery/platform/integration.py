"""Platform integration for ICYQuant service discovery.

Provides ``PlatformIntegration`` for connecting the service
discovery platform with other ICYQuant infrastructure modules:
configuration, secrets, crypto, plugin framework, feature
flags, event bus, and observability.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from .runtime_context import DiscoveryContext

logger = logging.getLogger(__name__)


class PlatformIntegration:
    """Integrates service discovery with platform infrastructure.

    Connects configuration, secrets, crypto, plugin framework,
    feature flags, event bus, and observability modules into
    the discovery context.

    Args:
        context: Optional ``DiscoveryContext`` instance.
    """

    def __init__(
        self, context: Optional[DiscoveryContext] = None
    ) -> None:
        self._lock = threading.RLock()
        self._context = context or DiscoveryContext()
        self._integrations: Dict[str, Any] = {}
        self._integration_count = 0
        self._last_result: Optional[Dict[str, Any]] = None

    def integrate(
        self,
        configuration: Any = None,
        secrets: Any = None,
        crypto: Any = None,
        plugin_framework: Any = None,
        feature_flags: Any = None,
        eventbus: Any = None,
        observability: Any = None,
    ) -> Dict[str, Any]:
        """Perform full platform integration.

        Args:
            configuration: Configuration manager.
            secrets: Secrets manager.
            crypto: Crypto provider.
            plugin_framework: Plugin framework instance.
            feature_flags: Feature flag service.
            eventbus: Event bus instance.
            observability: Observability suite.

        Returns:
            Integration result dictionary.
        """
        with self._lock:
            self._integration_count += 1

        connected: Dict[str, bool] = {}

        if configuration is not None:
            self._context.register("configuration", configuration)
            connected["configuration"] = True

        if secrets is not None:
            self._context.register("secrets", secrets)
            connected["secrets"] = True

        if crypto is not None:
            self._context.register("crypto", crypto)
            connected["crypto"] = True

        if plugin_framework is not None:
            self._context.register(
                "plugin_framework", plugin_framework
            )
            connected["plugin_framework"] = True

        if feature_flags is not None:
            self._context.register("feature_flags", feature_flags)
            connected["feature_flags"] = True

        if eventbus is not None:
            self._context.register("eventbus", eventbus)
            connected["eventbus"] = True

        if observability is not None:
            self._context.register("observability", observability)
            connected["observability"] = True

        result: Dict[str, Any] = {
            "integrated": True,
            "connected_modules": connected,
            "connected_count": len(connected),
            "timestamp": datetime.utcnow().isoformat(),
        }

        self._integrations = connected
        self._last_result = result

        logger.info(
            "Platform integration complete: %d modules connected.",
            len(connected),
        )
        return result

    def disconnect(self, module_name: str) -> bool:
        """Disconnect a module from the context.

        Args:
            module_name: Name of the module to disconnect.

        Returns:
            True if the module was found and disconnected.
        """
        with self._lock:
            if self._context.has(module_name):
                self._context.remove(module_name)
                self._integrations.pop(module_name, None)
                logger.info(
                    "Disconnected module '%s'.", module_name
                )
                return True
        return False

    def get_connected_modules(self) -> List[str]:
        with self._lock:
            return sorted(self._integrations.keys())

    def get_context(self) -> DiscoveryContext:
        return self._context

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "integration_count": self._integration_count,
                "connected_modules": sorted(
                    self._integrations.keys()
                ),
                "connected_count": len(self._integrations),
                "last_result": self._last_result,
                "context_components": (
                    self._context.list_components()
                ),
            }

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"PlatformIntegration(connected={len(self._integrations)}, "
                f"integrations={self._integration_count})"
            )
