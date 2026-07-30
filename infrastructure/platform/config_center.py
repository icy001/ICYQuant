"""
ICYQuant Infrastructure - Configuration Center

Centralized configuration management with multi-source resolution
and dynamic configuration updates.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
import logging
import os
import copy

logger = logging.getLogger(__name__)


class ConfigCenter:
    """
    Centralized configuration management.

    Supports:
    - Multi-source resolution (files, env vars, defaults)
    - Namespaced configuration
    - Dynamic updates with change notification
    """

    def __init__(self, config_dir: str = "configs"):
        self._config_dir = config_dir
        self._configs: Dict[str, Dict[str, Any]] = {}
        self._watchers: Dict[str, List[Callable]] = {}
        self._metadata: Dict[str, Dict[str, Any]] = {}

    def load_config(self, namespace: str, config: Dict[str, Any]):
        """Load configuration for a namespace."""
        self._configs[namespace] = copy.deepcopy(config)
        self._metadata[namespace] = {
            "loadedAt": datetime.now().isoformat(),
            "keys": list(config.keys()),
        }
        self._notify_watchers(namespace, config)
        logger.info(f"Config loaded: {namespace} ({len(config)} keys)")

    def get(self, namespace: str, key: Optional[str] = None, default: Any = None) -> Any:
        """Get configuration value."""
        config = self._configs.get(namespace, {})
        if key is None:
            return dict(config)
        return self._resolve_key(config, key, default)

    def _resolve_key(self, config: Dict, key: str, default: Any) -> Any:
        parts = key.split(".")
        value = config
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return default
            if value is None:
                return default
        return value

    def set(self, namespace: str, key: str, value: Any) -> bool:
        """Set a configuration value."""
        if namespace not in self._configs:
            self._configs[namespace] = {}
        self._set_key(self._configs[namespace], key, value)
        self._notify_watchers(namespace, self._configs[namespace])
        return True

    def _set_key(self, config: Dict, key: str, value: Any):
        parts = key.split(".")
        current = config
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value

    def delete(self, namespace: str, key: str) -> bool:
        """Delete a configuration key."""
        if namespace not in self._configs:
            return False
        config = self._configs[namespace]
        parts = key.split(".")
        current = config
        for part in parts[:-1]:
            if part not in current:
                return False
            current = current[part]
        if parts[-1] in current:
            del current[parts[-1]]
            self._notify_watchers(namespace, config)
            return True
        return False

    def merge_config(self, namespace: str, config: Dict[str, Any]):
        """Merge configuration into existing config."""
        existing = self._configs.get(namespace, {})
        merged = self._deep_merge(existing, config)
        self._configs[namespace] = merged
        self._notify_watchers(namespace, merged)

    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        result = copy.deepcopy(base)
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def watch(self, namespace: str, callback: Callable):
        """Watch for configuration changes."""
        if namespace not in self._watchers:
            self._watchers[namespace] = []
        self._watchers[namespace].append(callback)

    def _notify_watchers(self, namespace: str, config: Dict):
        for callback in self._watchers.get(namespace, []):
            try:
                callback(namespace, config)
            except Exception as e:
                logger.error(f"Config watcher error for {namespace}: {e}")

    def list_namespaces(self) -> List[str]:
        return list(self._configs.keys())

    def has_namespace(self, namespace: str) -> bool:
        return namespace in self._configs

    def get_metadata(self, namespace: str) -> Dict[str, Any]:
        return self._metadata.get(namespace, {})

    def get_status(self) -> Dict[str, Any]:
        return {
            "namespaces": list(self._configs.keys()),
            "totalConfigs": len(self._configs),
            "totalWatchers": sum(len(w) for w in self._watchers.values()),
        }

    def to_dict(self) -> Dict:
        return self.get_status()
