"""
ICYQuant Platform - Plugin Manager

Manages platform plugins: broker adapters, indicators, strategies, AI models.
Supports dynamic loading, hot swapping, and lifecycle management.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Type
from datetime import datetime
from enum import Enum
import logging
import importlib
import inspect
import uuid

logger = logging.getLogger(__name__)


class PluginState(str, Enum):
    DISCOVERED = "discovered"
    LOADED = "loaded"
    INITIALIZED = "initialized"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"
    UNLOADED = "unloaded"


class PluginType(str, Enum):
    BROKER = "broker"
    INDICATOR = "indicator"
    STRATEGY = "strategy"
    AI_MODEL = "ai_model"
    RISK_RULE = "risk_rule"
    DATA_SOURCE = "data_source"
    REPORT = "report"
    SECURITY = "security"
    UTILITY = "utility"


@dataclass
class PluginInfo:
    name: str
    plugin_type: PluginType
    version: str = "1.0.0"
    description: str = ""
    state: PluginState = PluginState.DISCOVERED
    module_path: str = ""
    class_name: str = ""
    instance: Optional[Any] = None
    config: Dict[str, Any] = field(default_factory=dict)
    error_message: str = ""
    installed_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "type": self.plugin_type.value,
            "version": self.version,
            "description": self.description,
            "state": self.state.value,
            "modulePath": self.module_path,
            "className": self.class_name,
            "error": self.error_message,
        }


class PluginManager:
    """
    Platform plugin manager.

    Supports dynamic discovery, loading, initialization,
    hot swapping, and lifecycle management of plugins.
    """

    def __init__(self):
        self._plugins: Dict[str, PluginInfo] = {}
        self._type_index: Dict[PluginType, List[str]] = {t: [] for t in PluginType}
        self._load_history: List[Dict] = []

    def register_plugin(
        self,
        name: str,
        plugin_type: PluginType,
        module_path: str = "",
        class_name: str = "",
        version: str = "1.0.0",
        description: str = "",
        config: Optional[Dict[str, Any]] = None,
    ) -> PluginInfo:
        if name in self._plugins:
            raise ValueError(f"Plugin '{name}' already registered")

        info = PluginInfo(
            name=name,
            plugin_type=plugin_type,
            version=version,
            description=description,
            module_path=module_path,
            class_name=class_name,
            config=config or {},
        )
        self._plugins[name] = info
        self._type_index[plugin_type].append(name)
        self._log_action("register", name, plugin_type.value)
        logger.info(f"Plugin registered: {name} ({plugin_type.value})")
        return info

    def load_plugin(self, name: str) -> bool:
        info = self._plugins.get(name)
        if not info:
            return False

        if info.module_path and info.class_name:
            try:
                module = importlib.import_module(info.module_path)
                cls = getattr(module, info.class_name)
                if inspect.isclass(cls):
                    info.instance = cls()
                info.state = PluginState.LOADED
                logger.info(f"Plugin loaded: {name}")
                return True
            except Exception as e:
                info.state = PluginState.ERROR
                info.error_message = str(e)
                logger.error(f"Failed to load plugin '{name}': {e}")
                return False
        else:
            info.state = PluginState.LOADED
            return True

    def initialize_plugin(self, name: str) -> bool:
        info = self._plugins.get(name)
        if not info or info.state != PluginState.LOADED:
            return False

        if info.instance and hasattr(info.instance, 'initialize'):
            try:
                info.instance.initialize(info.config)
                info.state = PluginState.INITIALIZED
                logger.info(f"Plugin initialized: {name}")
                return True
            except Exception as e:
                info.state = PluginState.ERROR
                info.error_message = str(e)
                return False

        info.state = PluginState.INITIALIZED
        return True

    def start_plugin(self, name: str) -> bool:
        info = self._plugins.get(name)
        if not info or info.state not in (PluginState.LOADED, PluginState.INITIALIZED):
            return False

        if info.state == PluginState.LOADED:
            self.initialize_plugin(name)

        if info.instance and hasattr(info.instance, 'start'):
            try:
                info.instance.start()
            except Exception as e:
                info.state = PluginState.ERROR
                info.error_message = str(e)
                return False

        info.state = PluginState.RUNNING
        logger.info(f"Plugin started: {name}")
        return True

    def stop_plugin(self, name: str) -> bool:
        info = self._plugins.get(name)
        if not info:
            return False

        if info.instance and hasattr(info.instance, 'stop'):
            try:
                info.instance.stop()
            except Exception:
                pass

        info.state = PluginState.PAUSED
        logger.info(f"Plugin stopped: {name}")
        return True

    def unload_plugin(self, name: str) -> bool:
        info = self._plugins.get(name)
        if not info:
            return False

        self.stop_plugin(name)
        info.state = PluginState.UNLOADED
        info.instance = None
        logger.info(f"Plugin unloaded: {name}")
        return True

    def reload_plugin(self, name: str) -> bool:
        """Hot-reload a plugin: unload then re-load."""
        info = self._plugins.get(name)
        if not info:
            return False

        self.unload_plugin(name)
        return self.load_plugin(name)

    def get_plugin(self, name: str) -> Optional[PluginInfo]:
        return self._plugins.get(name)

    def get_instance(self, name: str) -> Optional[Any]:
        info = self._plugins.get(name)
        return info.instance if info else None

    def get_by_type(self, plugin_type: PluginType) -> List[PluginInfo]:
        return [self._plugins[n] for n in self._type_index.get(plugin_type, [])]

    def get_running(self) -> List[PluginInfo]:
        return [p for p in self._plugins.values() if p.state == PluginState.RUNNING]

    def discover_plugins(self, search_paths: Optional[List[str]] = None) -> List[str]:
        """Discover available plugins from search paths."""
        discovered = []
        if search_paths:
            for path in search_paths:
                discovered.append(f"Found plugins in {path}")
        logger.info(f"Discovered {len(discovered)} plugin paths")
        return discovered

    def list_names(self) -> List[str]:
        return list(self._plugins.keys())

    def list_types(self) -> List[PluginType]:
        return [t for t, names in self._type_index.items() if names]

    def _log_action(self, action: str, name: str, detail: str):
        self._load_history.append({
            "action": action,
            "plugin": name,
            "detail": detail,
            "timestamp": datetime.now().isoformat(),
        })

    def get_status(self) -> Dict:
        by_state = {}
        for p in self._plugins.values():
            s = p.state.value
            by_state[s] = by_state.get(s, 0) + 1
        return {
            "total": len(self._plugins),
            "byState": by_state,
            "byType": {t.value: len(names) for t, names in self._type_index.items() if names},
            "running": sum(1 for p in self._plugins.values() if p.state == PluginState.RUNNING),
        }

    def to_dict(self) -> Dict:
        return {
            "plugins": [p.to_dict() for p in self._plugins.values()],
            "status": self.get_status(),
        }
