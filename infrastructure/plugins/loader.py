"""Plugin loader.

Loads and imports plugins from entry points, supporting module loading
by path, plugin class discovery, and instantiation with context.
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from .exceptions import PluginLoadError, PluginNotFoundError

logger = logging.getLogger(__name__)


class PluginLoader:
    """Loads plugin modules and instantiates plugin classes.

    Supports:
    - Entry point import
    - Module loading by path
    - Plugin class discovery
    - Plugin instantiation with context
    """

    def __init__(self) -> None:
        self._loaded_modules: Dict[str, Any] = {}
        self._stats: Dict[str, int] = {
            "modules_loaded": 0,
            "plugins_instantiated": 0,
            "discoveries": 0,
            "errors": 0,
        }

    def load_module(self, module_path: str) -> Any:
        try:
            if module_path in self._loaded_modules:
                logger.debug("Module '%s' already loaded; returning cached.", module_path)
                return self._loaded_modules[module_path]
            module = importlib.import_module(module_path)
            self._loaded_modules[module_path] = module
            self._stats["modules_loaded"] += 1
            logger.info("Loaded module '%s'.", module_path)
            return module
        except ImportError as e:
            self._stats["errors"] += 1
            raise PluginLoadError(f"Failed to import module '{module_path}': {e}") from e
        except Exception as e:
            self._stats["errors"] += 1
            raise PluginLoadError(f"Unexpected error loading module '{module_path}': {e}") from e

    def discover_plugin_class(self, module: Any) -> Optional[type]:
        if module is None:
            return None
        from .models import Plugin
        plugin_class: Optional[type] = None
        for attr_name in dir(module):
            if attr_name.startswith("_"):
                continue
            try:
                attr = getattr(module, attr_name)
            except Exception:
                continue
            if not isinstance(attr, type):
                continue
            if attr is Plugin:
                continue
            if issubclass(attr, Plugin):
                if plugin_class is None:
                    plugin_class = attr
                else:
                    logger.warning(
                        "Multiple Plugin subclasses found in module '%s'; using '%s'.",
                        getattr(module, "__name__", str(module)),
                        plugin_class.__name__,
                    )
        self._stats["discoveries"] += 1
        return plugin_class

    def instantiate(self, plugin_class: type, context: Any = None) -> Any:
        if plugin_class is None:
            raise PluginLoadError("Cannot instantiate: plugin_class is None.")
        try:
            if context is not None:
                return plugin_class(context=context)
            return plugin_class()
        except TypeError:
            try:
                return plugin_class()
            except Exception as e:
                self._stats["errors"] += 1
                raise PluginLoadError(
                    f"Failed to instantiate '{plugin_class.__name__}': {e}"
                ) from e
        except Exception as e:
            self._stats["errors"] += 1
            raise PluginLoadError(
                f"Failed to instantiate '{plugin_class.__name__}': {e}"
            ) from e
        finally:
            self._stats["plugins_instantiated"] += 1

    async def load_plugin(self, entrypoint: str, context: Any = None) -> Any:
        if not entrypoint:
            raise PluginNotFoundError("Entrypoint cannot be empty.")
        parts = entrypoint.rsplit(":", 1) if ":" in entrypoint else [entrypoint]
        if len(parts) == 2:
            module_path, class_name = parts
        else:
            module_path = parts[0]
            class_name = None
        try:
            module = self.load_module(module_path)
        except PluginLoadError:
            raise
        if class_name is not None:
            plugin_class = getattr(module, class_name, None)
            if plugin_class is None:
                self._stats["errors"] += 1
                raise PluginNotFoundError(
                    f"Class '{class_name}' not found in module '{module_path}'."
                )
        else:
            plugin_class = self.discover_plugin_class(module)
            if plugin_class is None:
                self._stats["errors"] += 1
                raise PluginNotFoundError(
                    f"No Plugin subclass found in module '{module_path}'."
                )
        instance = self.instantiate(plugin_class, context=context)
        logger.info("Plugin '%s' loaded successfully via entrypoint '%s'.", plugin_class, entrypoint)
        return instance

    def get_available_plugins(self, search_paths: List[str] = None) -> List[str]:
        if search_paths is None:
            search_paths = ["."]
        discovered: List[str] = []
        for path_str in search_paths:
            path = Path(path_str)
            if not path.exists():
                logger.debug("Search path '%s' does not exist; skipping.", path_str)
                continue
            if path.is_file() and path.suffix == ".py":
                discovered.append(str(path))
                continue
            if path.is_dir():
                for py_file in sorted(path.rglob("*.py")):
                    if py_file.name.startswith("_"):
                        continue
                    discovered.append(str(py_file))
        return sorted(set(discovered))

    def validate_entrypoint(self, entrypoint: str) -> bool:
        if not entrypoint or not isinstance(entrypoint, str):
            return False
        if ":" in entrypoint:
            parts = entrypoint.split(":")
            if len(parts) != 2:
                return False
            module_path, class_name = parts
            if not module_path or not class_name:
                return False
            if not module_path.replace(".", "").replace("_", "").isalnum():
                return False
            if not class_name.isidentifier():
                return False
        else:
            if not entrypoint.replace(".", "").replace("_", "").isalnum():
                return False
        return True

    def get_stats(self) -> Dict[str, Any]:
        return {
            "modules_loaded": len(self._loaded_modules),
            "module_paths": list(self._loaded_modules.keys()),
            "stats": dict(self._stats),
        }