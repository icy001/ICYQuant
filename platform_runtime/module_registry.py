"""
ICYQuant Platform - Module Registry

Central registry for all platform modules.
Supports dynamic discovery, lifecycle state tracking, and metadata management.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from enum import Enum
import logging
import uuid

logger = logging.getLogger(__name__)


class ModuleState(str, Enum):
    REGISTERED = "registered"
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    DEGRADED = "degraded"
    STOPPED = "stopped"
    ERROR = "error"


class ModuleType(str, Enum):
    CORE = "core"
    DATA = "data"
    TRADING = "trading"
    RISK = "risk"
    AI = "ai"
    RESEARCH = "research"
    PORTFOLIO = "portfolio"
    INFRASTRUCTURE = "infrastructure"
    OBSERVABILITY = "observability"
    SECURITY = "security"
    EXTENSION = "extension"


@dataclass
class ModuleInfo:
    name: str
    module_type: ModuleType
    version: str = "1.0.0"
    description: str = ""
    state: ModuleState = ModuleState.REGISTERED
    dependencies: List[str] = field(default_factory=list)
    health_check: Optional[Callable[[], bool]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    registered_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    error_message: str = ""
    instance: Optional[Any] = None

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "type": self.module_type.value,
            "version": self.version,
            "description": self.description,
            "state": self.state.value,
            "dependencies": self.dependencies,
            "startedAt": self.started_at.isoformat() if self.started_at else None,
            "errorMessage": self.error_message,
        }


class ModuleRegistry:
    """
    Central module registry for the platform.

    Manages registration, discovery, and state tracking of all modules.
    Supports health checks and dependency-based ordering.
    """

    def __init__(self):
        self._modules: Dict[str, ModuleInfo] = {}
        self._type_index: Dict[ModuleType, List[str]] = {t: [] for t in ModuleType}
        self._lock = None

    def register(
        self,
        name: str,
        module_type: ModuleType,
        version: str = "1.0.0",
        description: str = "",
        dependencies: Optional[List[str]] = None,
        health_check: Optional[Callable[[], bool]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        instance: Optional[Any] = None,
    ) -> ModuleInfo:
        if name in self._modules:
            raise ValueError(f"Module '{name}' already registered")

        info = ModuleInfo(
            name=name,
            module_type=module_type,
            version=version,
            description=description,
            dependencies=dependencies or [],
            health_check=health_check,
            metadata=metadata or {},
            instance=instance,
        )
        self._modules[name] = info
        self._type_index[module_type].append(name)
        logger.info(f"Module registered: {name} ({module_type.value})")
        return info

    def unregister(self, name: str) -> bool:
        if name not in self._modules:
            return False
        info = self._modules.pop(name)
        if name in self._type_index[info.module_type]:
            self._type_index[info.module_type].remove(name)
        logger.info(f"Module unregistered: {name}")
        return True

    def get_module(self, name: str) -> Optional[ModuleInfo]:
        return self._modules.get(name)

    def get_instance(self, name: str) -> Optional[Any]:
        info = self._modules.get(name)
        return info.instance if info else None

    def set_state(self, name: str, state: ModuleState, error_message: str = ""):
        info = self._modules.get(name)
        if not info:
            raise KeyError(f"Module '{name}' not found")
        info.state = state
        info.error_message = error_message
        if state == ModuleState.RUNNING:
            info.started_at = datetime.now()
        logger.debug(f"Module '{name}' state: {state.value}")

    def get_all(self) -> List[ModuleInfo]:
        return list(self._modules.values())

    def get_by_type(self, module_type: ModuleType) -> List[ModuleInfo]:
        return [self._modules[n] for n in self._type_index.get(module_type, [])]

    def get_by_state(self, state: ModuleState) -> List[ModuleInfo]:
        return [m for m in self._modules.values() if m.state == state]

    def get_running(self) -> List[ModuleInfo]:
        return self.get_by_state(ModuleState.RUNNING)

    def get_failed(self) -> List[ModuleInfo]:
        return self.get_by_state(ModuleState.ERROR)

    def check_health(self) -> Dict[str, bool]:
        results = {}
        for name, info in self._modules.items():
            if info.health_check:
                try:
                    results[name] = info.health_check()
                except Exception:
                    results[name] = False
            else:
                results[name] = info.state == ModuleState.RUNNING
        return results

    def ordered_by_dependencies(self) -> List[ModuleInfo]:
        from .dependency_graph import DependencyGraph
        graph = DependencyGraph()
        for name, info in self._modules.items():
            graph.add_node(name, info.module_type, info.dependencies)
        order = graph.resolve_startup_order()
        return [self._modules[n] for n in order if n in self._modules]

    def list_names(self) -> List[str]:
        return list(self._modules.keys())

    def count(self) -> int:
        return len(self._modules)

    def get_status(self) -> Dict:
        all_modules = list(self._modules.values())
        by_state = {}
        for m in all_modules:
            state = m.state.value
            by_state[state] = by_state.get(state, 0) + 1
        return {
            "total": len(all_modules),
            "byState": by_state,
            "byType": {t.value: len(names) for t, names in self._type_index.items() if names},
            "healthy": sum(1 for m in all_modules if m.state == ModuleState.RUNNING),
        }

    def to_dict(self) -> Dict:
        return {
            "modules": [m.to_dict() for m in self._modules.values()],
            "status": self.get_status(),
        }
