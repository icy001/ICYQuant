from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
import copy
import logging

logger = logging.getLogger(__name__)


@dataclass
class PluginConfig:
    plugin_id: str
    default: Dict[str, Any] = field(default_factory=dict)
    overrides: Dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        """Return override value first, then default, then ``default``."""
        if key in self.overrides:
            return self.overrides[key]
        if key in self.default:
            return self.default[key]
        return default

    def set(self, key: str, value: Any) -> None:
        """Set an override value."""
        self.overrides[key] = value

    def all(self) -> Dict[str, Any]:
        """Return the merged configuration (override > default)."""
        merged = copy.deepcopy(self.default)
        merged.update(copy.deepcopy(self.overrides))
        return merged

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "default": copy.deepcopy(self.default),
            "overrides": copy.deepcopy(self.overrides),
        }


class ConfigurationManager:
    """Manages plugin configurations with hot reload support."""

    def __init__(self) -> None:
        self._configs: Dict[str, PluginConfig] = {}
        self._listeners: Dict[str, List[Callable[[dict], None]]] = {}

    def register(self, plugin_id: str, default_config: dict) -> PluginConfig:
        config = PluginConfig(
            plugin_id=plugin_id,
            default=copy.deepcopy(default_config),
        )
        self._configs[plugin_id] = config
        return config

    def unregister(self, plugin_id: str) -> None:
        self._configs.pop(plugin_id, None)
        self._listeners.pop(plugin_id, None)

    def get_config(self, plugin_id: str) -> Optional[PluginConfig]:
        return self._configs.get(plugin_id)

    def get_value(self, plugin_id: str, key: str, default: Any = None) -> Any:
        config = self._configs.get(plugin_id)
        if config is None:
            return default
        return config.get(key, default)

    def set_override(self, plugin_id: str, key: str, value: Any) -> None:
        config = self._configs.get(plugin_id)
        if config is None:
            return
        config.set(key, value)
        self._notify(plugin_id, config.all())

    def reload(self, plugin_id: str, config: dict) -> None:
        existing = self._configs.get(plugin_id)
        if existing is None:
            return
        existing.default = copy.deepcopy(config)
        existing.overrides = {}
        self._notify(plugin_id, existing.all())

    def reload_all(self, configs: Dict[str, dict]) -> None:
        for plugin_id, config in configs.items():
            self.reload(plugin_id, config)

    def list_configs(self) -> Dict[str, dict]:
        return {pid: cfg.all() for pid, cfg in self._configs.items()}

    def add_listener(self, plugin_id: str, callback: Callable[[dict], None]) -> None:
        self._listeners.setdefault(plugin_id, []).append(callback)

    def _notify(self, plugin_id: str, config: dict) -> None:
        for callback in self._listeners.get(plugin_id, []):
            try:
                callback(config)
            except Exception:
                logger.exception("Config listener for plugin %s failed", plugin_id)
