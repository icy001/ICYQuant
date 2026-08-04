"""Plugin data models.

Defines the core data structures used by the ICYQuant plugin framework,
including plugin lifecycle state, priority ordering, and the Plugin
dataclass with serialization support.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class PluginState(Enum):
    """Lifecycle state of a plugin."""

    REGISTERED = "registered"
    LOADED = "loaded"
    INITIALIZED = "initialized"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"
    UNINSTALLED = "uninstalled"


class PluginPriority(Enum):
    """Priority ordering for plugin lifecycle operations.

    Lower values indicate higher priority.
    """

    CRITICAL = 0
    HIGH = 10
    NORMAL = 50
    LOW = 90
    BACKGROUND = 100


def _parse_datetime(value: Any) -> Optional[datetime]:
    """Parse a value into a datetime, returning None on failure."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None


@dataclass
class Plugin:
    """A registered plugin with lifecycle metadata.

    The ``instance`` field holds the live plugin object (if any) and is
    excluded from serialization since it may not be serializable.
    """

    id: str
    name: str
    version: str
    author: str
    description: str = ""
    entrypoint: str = ""
    api_version: str = "v1"
    state: PluginState = PluginState.REGISTERED
    priority: PluginPriority = PluginPriority.NORMAL
    capabilities: List[str] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    instance: Any = None
    installed_at: Optional[datetime] = None
    loaded_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the plugin to a dictionary.

        The ``instance`` field is omitted. Datetime fields are serialized
        as ISO 8601 strings, and enums as their values.
        """
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "author": self.author,
            "description": self.description,
            "entrypoint": self.entrypoint,
            "api_version": self.api_version,
            "state": self.state.value,
            "priority": self.priority.value,
            "capabilities": list(self.capabilities),
            "permissions": list(self.permissions),
            "dependencies": list(self.dependencies),
            "config": dict(self.config),
            "metadata": dict(self.metadata),
            "installed_at": self.installed_at.isoformat() if self.installed_at else None,
            "loaded_at": self.loaded_at.isoformat() if self.loaded_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "stopped_at": self.stopped_at.isoformat() if self.stopped_at else None,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Plugin:
        """Deserialize a plugin from a dictionary."""
        if data is None:
            data = {}

        raw_state = data.get("state", PluginState.REGISTERED.value)
        if isinstance(raw_state, PluginState):
            state = raw_state
        else:
            state = PluginState(str(raw_state))

        raw_priority = data.get("priority", PluginPriority.NORMAL.value)
        if isinstance(raw_priority, PluginPriority):
            priority = raw_priority
        else:
            priority = PluginPriority(int(raw_priority))

        return cls(
            id=str(data.get("id", "")),
            name=str(data.get("name", "")),
            version=str(data.get("version", "")),
            author=str(data.get("author", "")),
            description=str(data.get("description", "")),
            entrypoint=str(data.get("entrypoint", "")),
            api_version=str(data.get("api_version", "v1")),
            state=state,
            priority=priority,
            capabilities=list(data.get("capabilities", []) or []),
            permissions=list(data.get("permissions", []) or []),
            dependencies=list(data.get("dependencies", []) or []),
            config=dict(data.get("config", {}) or {}),
            metadata=dict(data.get("metadata", {}) or {}),
            installed_at=_parse_datetime(data.get("installed_at")),
            loaded_at=_parse_datetime(data.get("loaded_at")),
            started_at=_parse_datetime(data.get("started_at")),
            stopped_at=_parse_datetime(data.get("stopped_at")),
            error=data.get("error"),
        )


@dataclass
class PluginInstance:
    """A runtime instance of a plugin."""

    plugin_id: str
    instance_id: str
    state: PluginState
    started_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PluginInfo:
    """Lightweight plugin info for listing."""

    id: str
    name: str
    version: str
    state: str
    author: str
    description: str
