"""
ICYQuant Infrastructure - Module Loader

Handles dynamic loading, unloading, and reloading of platform modules.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Any, Type
from datetime import datetime
import logging
import importlib
import inspect
import sys

logger = logging.getLogger(__name__)


class ModuleLoader:
    """
    Dynamic module loader for the platform.

    Supports:
    - Dynamic import by path
    - Class discovery and instantiation
    - Hot-reloading of modules
    - Module caching
    """

    def __init__(self):
        self._loaded_modules: Dict[str, Any] = {}
        self._module_classes: Dict[str, Dict[str, Type]] = {}
        self._load_history: List[Dict] = []

    def load_module(self, module_path: str) -> Optional[Any]:
        """Dynamically import a module by its Python path."""
        try:
            if module_path in self._loaded_modules:
                return self._loaded_modules[module_path]

            module = importlib.import_module(module_path)
            self._loaded_modules[module_path] = module
            self._log_load(module_path, "loaded")
            logger.info(f"Module loaded: {module_path}")
            return module
        except ImportError as e:
            logger.error(f"Failed to load module '{module_path}': {e}")
            self._log_load(module_path, f"error: {e}")
            return None

    def reload_module(self, module_path: str) -> Optional[Any]:
        """Hot-reload a previously loaded module."""
        try:
            if module_path in self._loaded_modules:
                module = self._loaded_modules[module_path]
                reloaded = importlib.reload(module)
                self._loaded_modules[module_path] = reloaded
                self._log_load(module_path, "reloaded")
                logger.info(f"Module reloaded: {module_path}")
                return reloaded
            return self.load_module(module_path)
        except Exception as e:
            logger.error(f"Failed to reload module '{module_path}': {e}")
            self._log_load(module_path, f"error: {e}")
            return None

    def unload_module(self, module_path: str) -> bool:
        """Unload a module from cache."""
        if module_path in self._loaded_modules:
            del self._loaded_modules[module_path]
            self._log_load(module_path, "unloaded")
            return True
        return False

    def discover_classes(
        self,
        module_path: str,
        base_class: Optional[Type] = None,
    ) -> List[Dict[str, str]]:
        """Discover classes in a module, optionally filtered by base class."""
        module = self._loaded_modules.get(module_path)
        if not module:
            module = self.load_module(module_path)
        if not module:
            return []

        classes = []
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if obj.__module__ == module_path:
                if base_class is None or issubclass(obj, base_class):
                    classes.append({
                        "name": name,
                        "module": module_path,
                        "bases": [b.__name__ for b in obj.__bases__],
                    })
        return classes

    def instantiate_class(
        self,
        module_path: str,
        class_name: str,
        *args,
        **kwargs,
    ) -> Optional[Any]:
        """Instantiate a class from a loaded module."""
        module = self._loaded_modules.get(module_path)
        if not module:
            return None

        cls = getattr(module, class_name, None)
        if cls is None:
            return None

        return cls(*args, **kwargs)

    def get_loaded(self) -> Dict[str, Any]:
        return dict(self._loaded_modules)

    def list_loaded(self) -> List[str]:
        return list(self._loaded_modules.keys())

    def is_loaded(self, module_path: str) -> bool:
        return module_path in self._loaded_modules

    def _log_load(self, module_path: str, action: str):
        self._load_history.append({
            "module": module_path,
            "action": action,
            "timestamp": datetime.now().isoformat(),
        })

    def get_history(self, limit: int = 50) -> List[Dict]:
        return self._load_history[-limit:]

    def get_status(self) -> Dict[str, Any]:
        return {
            "loadedModules": list(self._loaded_modules.keys()),
            "totalLoaded": len(self._loaded_modules),
            "totalLoads": len(self._load_history),
        }

    def to_dict(self) -> Dict:
        return self.get_status()
