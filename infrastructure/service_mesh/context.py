"""Mesh context for unified component access.

Provides ``MeshContext`` as the central dependency injection
point for all service mesh components, mirroring the pattern
used by DiscoveryContext in the Service Discovery platform.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class MeshContext:
    """Central context for the service mesh.

    All mesh components access shared resources through this
    context: configuration, control plane, data plane, registry,
    eventbus, and metrics.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._components: Dict[str, Any] = {}
        self._config: Dict[str, Any] = {}
        self._metadata: Dict[str, Any] = {}

    def register(self, name: str, component: Any) -> None:
        """Register a component in the context."""
        with self._lock:
            self._components[name] = component
        logger.debug("Mesh context registered: %s", name)

    def get(self, name: str, default: Any = None) -> Any:
        """Get a component from the context."""
        with self._lock:
            return self._components.get(name, default)

    def has(self, name: str) -> bool:
        """Check if a component exists in the context."""
        with self._lock:
            return name in self._components

    def set_config(self, key: str, value: Any) -> None:
        """Set a configuration value."""
        with self._lock:
            self._config[key] = value

    def get_config(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        with self._lock:
            return self._config.get(key, default)

    def set_metadata(self, key: str, value: Any) -> None:
        """Set mesh metadata."""
        with self._lock:
            self._metadata[key] = value

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get mesh metadata."""
        with self._lock:
            return self._metadata.get(key, default)

    def get_all_components(self) -> Dict[str, Any]:
        """Get all registered components."""
        with self._lock:
            return dict(self._components)

    def get_all_config(self) -> Dict[str, Any]:
        """Get all configuration."""
        with self._lock:
            return dict(self._config)

    def clear(self) -> None:
        """Clear all components and configuration."""
        with self._lock:
            self._components.clear()
            self._config.clear()
            self._metadata.clear()

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "component_count": len(self._components),
                "config_count": len(self._config),
                "metadata_count": len(self._metadata),
                "components": list(self._components.keys()),
            }

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"MeshContext(components={len(self._components)}, "
                f"config={len(self._config)})"
            )
