"""Module registration and discovery."""
from __future__ import annotations
import importlib
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Type

from shared.constants import ModuleType

logger = logging.getLogger(__name__)

@dataclass
class ModuleInfo:
    name: str
    module_type: ModuleType
    version: str = "1.0.0"
    description: str = ""
    dependencies: List[str] = field(default_factory=list)
    instance: Any = None
    is_initialized: bool = False
    is_running: bool = False

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "type": self.module_type.value,
            "version": self.version,
            "description": self.description,
            "dependencies": self.dependencies,
            "initialized": self.is_initialized,
            "running": self.is_running,
        }

class ModuleRegistry:
    """Central registry for all platform modules."""

    def __init__(self):
        self._modules: Dict[str, ModuleInfo] = {}
        self._entry_points: Dict[str, str] = {}

    def register(
        self,
        name: str,
        module_type: ModuleType,
        version: str = "1.0.0",
        description: str = "",
        dependencies: Optional[List[str]] = None,
        entry_point: Optional[str] = None,
    ) -> ModuleInfo:
        info = ModuleInfo(
            name=name,
            module_type=module_type,
            version=version,
            description=description,
            dependencies=dependencies or [],
        )
        self._modules[name] = info
        if entry_point:
            self._entry_points[name] = entry_point
        logger.info(f"Registered module: {name} ({module_type.value})")
        return info

    def unregister(self, name: str) -> None:
        self._modules.pop(name, None)
        self._entry_points.pop(name, None)

    def get(self, name: str) -> Optional[ModuleInfo]:
        return self._modules.get(name)

    def get_instance(self, name: str) -> Optional[Any]:
        info = self._modules.get(name)
        return info.instance if info else None

    def set_instance(self, name: str, instance: Any) -> None:
        if name in self._modules:
            self._modules[name].instance = instance

    def list_modules(self, module_type: Optional[ModuleType] = None) -> List[ModuleInfo]:
        modules = list(self._modules.values())
        if module_type:
            modules = [m for m in modules if m.module_type == module_type]
        return modules

    def get_all(self) -> Dict[str, ModuleInfo]:
        return dict(self._modules)

    def ordered_by_dependencies(self) -> List[ModuleInfo]:
        visited: set = set()
        result: List[ModuleInfo] = []
        modules = self._modules

        def visit(name: str) -> None:
            if name in visited:
                return
            visited.add(name)
            info = modules.get(name)
            if not info:
                return
            for dep in info.dependencies:
                if dep in modules:
                    visit(dep)
            result.append(info)

        for name in modules:
            visit(name)

        return result

    def load_entry_point(self, name: str) -> Optional[Any]:
        entry = self._entry_points.get(name)
        if not entry:
            return None
        try:
            module_path, attr = entry.rsplit(".", 1)
            module = importlib.import_module(module_path)
            factory = getattr(module, attr)
            return factory()
        except Exception as e:
            logger.error(f"Failed to load entry point for {name}: {e}")
            return None

    def get_status(self) -> dict:
        return {
            "total_modules": len(self._modules),
            "modules": {n: m.to_dict() for n, m in self._modules.items()},
            "by_type": self._group_by_type(),
        }

    def _group_by_type(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for info in self._modules.values():
            key = info.module_type.value
            counts[key] = counts.get(key, 0) + 1
        return counts

    def __len__(self) -> int:
        return len(self._modules)

    def __contains__(self, name: str) -> bool:
        return name in self._modules

    def __iter__(self):
        return iter(self._modules.values())
