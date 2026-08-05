"""Runtime context for ICYQuant service discovery platform.

Provides ``DiscoveryContext`` as a unified context object that
holds references to all core components: configuration, registry,
resolver, event bus, metrics, tracing, and feature flags.
"""

from __future__ import annotations

import threading
from datetime import datetime
from typing import Any, Dict, Optional


class DiscoveryContext:
    """Unified context for discovery sub-modules.

    Holds references to all core platform components so that
    any module can access them via a single context object.
    Supports dictionary-like access and attribute access.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._components: Dict[str, Any] = {}
        self._created_at = datetime.utcnow()
        self._metadata: Dict[str, Any] = {}

    def register(
        self, name: str, component: Any
    ) -> None:
        if not name:
            raise ValueError("component name cannot be empty")
        with self._lock:
            self._components[name] = component

    def get(self, name: str, default: Any = None) -> Any:
        with self._lock:
            return self._components.get(name, default)

    def has(self, name: str) -> bool:
        with self._lock:
            return name in self._components

    def remove(self, name: str) -> bool:
        with self._lock:
            if name in self._components:
                del self._components[name]
                return True
            return False

    @property
    def configuration(self) -> Any:
        return self.get("configuration")

    @property
    def registry(self) -> Any:
        return self.get("registry")

    @property
    def resolver(self) -> Any:
        return self.get("resolver")

    @property
    def eventbus(self) -> Any:
        return self.get("eventbus")

    @property
    def metrics(self) -> Any:
        return self.get("metrics")

    @property
    def tracing(self) -> Any:
        return self.get("tracing")

    @property
    def feature_flags(self) -> Any:
        return self.get("feature_flags")

    @property
    def heartbeat(self) -> Any:
        return self.get("heartbeat")

    @property
    def ha_controller(self) -> Any:
        return self.get("ha_controller")

    @property
    def gateway(self) -> Any:
        return self.get("gateway")

    @property
    def cluster(self) -> Any:
        return self.get("cluster")

    @property
    def scheduler(self) -> Any:
        return self.get("scheduler")

    @property
    def platform(self) -> Any:
        return self.get("platform")

    def set_metadata(self, key: str, value: Any) -> None:
        with self._lock:
            self._metadata[key] = value

    def get_metadata(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._metadata.get(key, default)

    def list_components(self) -> list:
        with self._lock:
            return sorted(self._components.keys())

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "created_at": self._created_at.isoformat(),
                "components": sorted(self._components.keys()),
                "metadata": dict(self._metadata),
            }

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "component_count": len(self._components),
                "components": sorted(self._components.keys()),
                "metadata_keys": sorted(self._metadata.keys()),
                "uptime_seconds": (
                    datetime.utcnow() - self._created_at
                ).total_seconds(),
            }

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"DiscoveryContext(components={len(self._components)}, "
                f"created_at={self._created_at.isoformat()})"
            )
