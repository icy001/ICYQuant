"""Dynamic import engine for the plugin loader subsystem.

Provides synchronous module import utilities supporting both dotted
module paths (via ``importlib.import_module``) and file paths. Loaded
modules are cached and protected by a lock for thread safety.

The importer discovers plugin classes within imported modules and
instantiates them with an optional context.
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import os
import sys
import threading
import time
import types
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_PLUGIN_METHOD_HINTS = ("execute", "run", "start", "handle", "process", "main")


class PluginImporter:
    """Imports plugin modules and discovers plugin classes.

    Maintains a cache of loaded modules keyed by module path.
    Thread-safe via a single reentrant lock guarding all cache
    operations.
    """

    def __init__(self) -> None:
        self._loaded_modules: Dict[str, types.ModuleType] = {}
        self._lock = threading.RLock()
        self._stats: Dict[str, int] = {
            "imports": 0,
            "cache_hits": 0,
            "errors": 0,
            "instances_created": 0,
            "reloads": 0,
            "unloads": 0,
        }

    def import_module(self, module_path: str) -> types.ModuleType:
        """Import a module by its dotted path, with caching.

        Args:
            module_path: Dotted module path (e.g. ``"json"`` or
                ``"mypkg.sub.module"``).

        Returns:
            The imported module.

        Raises:
            ImportError: If the module cannot be imported.
            ValueError: If the module path is empty.
        """
        if not module_path:
            raise ValueError("Module path cannot be empty")

        with self._lock:
            cached = self._loaded_modules.get(module_path)
            if cached is not None:
                self._stats["cache_hits"] += 1
                return cached

        try:
            module = importlib.import_module(module_path)
        except Exception as exc:
            with self._lock:
                self._stats["errors"] += 1
            logger.exception("Failed to import module '%s'", module_path)
            raise ImportError(
                f"Failed to import module '{module_path}': {exc}"
            ) from exc

        with self._lock:
            self._loaded_modules[module_path] = module
            self._stats["imports"] += 1

        logger.debug("Imported module '%s'.", module_path)
        return module

    def discover_plugin_class(
        self, module: types.ModuleType
    ) -> Optional[type]:
        """Discover a plugin class within a module.

        Scans the module's attributes for classes that are defined
        locally (not imported) and exhibit plugin-like behaviour
        (i.e. expose a recognised plugin method). The best match
        is returned, or ``None`` if no candidate is found.

        Args:
            module: The module to scan.

        Returns:
            A plugin class, or ``None``.
        """
        if module is None:
            return None

        candidates: List[type] = []
        module_file = getattr(module, "__file__", None)

        for name in dir(module):
            if name.startswith("_"):
                continue
            obj = getattr(module, name, None)
            if not isinstance(obj, type):
                continue
            if obj.__module__ != module.__name__:
                continue
            if obj is type:
                continue

            if self._looks_like_plugin_class(obj):
                candidates.append(obj)

        if not candidates:
            return None

        direct = [
            c
            for c in candidates
            if any(
                hasattr(base, name)
                for base in c.__mro__
                for name in _PLUGIN_METHOD_HINTS
                if name in base.__dict__
            )
        ]
        if direct:
            return direct[0]
        return candidates[0]

    def instantiate(self, plugin_class: type, context: Any = None) -> Any:
        """Instantiate a plugin class with an optional context.

        If ``context`` is provided, it is passed as the sole positional
        argument. Otherwise the class is instantiated with no args.
        Falls back to no-arg construction if a TypeError is raised.

        Args:
            plugin_class: The class to instantiate.
            context: Optional context passed to the constructor.

        Returns:
            The instantiated plugin object.

        Raises:
            ValueError: If ``plugin_class`` is ``None``.
        """
        if plugin_class is None:
            raise ValueError("Plugin class cannot be None")

        try:
            if context is not None:
                instance = plugin_class(context)
            else:
                instance = plugin_class()
            self._stats["instances_created"] += 1
            return instance
        except TypeError:
            instance = plugin_class()
            self._stats["instances_created"] += 1
            return instance

    def load_plugin(self, entrypoint: str, context: Any = None) -> Any:
        """Load a plugin from an entrypoint string.

        Accepts a dotted module path, a ``"module:Class"`` reference,
        or a file path. The module is imported, a plugin class is
        discovered (or the specified class is looked up), and the
        class is instantiated with the optional context.

        Args:
            entrypoint: Entrypoint string (e.g. ``"json"``,
                ``"mypkg.plugin:MyPlugin"``).
            context: Optional context passed to the plugin constructor.

        Returns:
            The instantiated plugin, or ``None`` if loading fails.

        Raises:
            ImportError: If the module cannot be imported.
            ValueError: If the entrypoint is empty.
        """
        if not entrypoint:
            raise ValueError("Entrypoint cannot be empty")

        start = time.monotonic()
        module_path = entrypoint
        class_name: Optional[str] = None

        if ":" in entrypoint:
            parts = entrypoint.split(":", 1)
            module_path = parts[0]
            class_name = parts[1] if len(parts) > 1 else None

        try:
            if self._looks_like_file_path(module_path):
                module = self._import_from_file(module_path)
            else:
                module = self.import_module(module_path)
        except Exception:
            elapsed = (time.monotonic() - start) * 1000.0
            logger.exception("Failed to import entrypoint '%s'", entrypoint)
            return None

        plugin_class: Optional[type] = None
        if class_name:
            plugin_class = getattr(module, class_name, None)
            if plugin_class is not None and not isinstance(plugin_class, type):
                plugin_class = None
        else:
            plugin_class = self.discover_plugin_class(module)

        if plugin_class is None:
            logger.warning(
                "No plugin class found in entrypoint '%s'", entrypoint
            )
            return None

        try:
            instance = self.instantiate(plugin_class, context)
            elapsed = (time.monotonic() - start) * 1000.0
            logger.info(
                "Loaded plugin '%s' in %.2f ms.", entrypoint, elapsed
            )
            return instance
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000.0
            logger.exception(
                "Failed to instantiate plugin from '%s': %s", entrypoint, exc
            )
            return None

    def unload_module(self, module_path: str) -> None:
        """Remove a module from the internal cache and ``sys.modules``.

        Args:
            module_path: The module path to unload.
        """
        with self._lock:
            removed = False
            if module_path in self._loaded_modules:
                del self._loaded_modules[module_path]
                removed = True

            if module_path in sys.modules:
                del sys.modules[module_path]
                removed = True

            if removed:
                self._stats["unloads"] += 1
                logger.debug("Unloaded module '%s'.", module_path)

    def reload_module(self, module_path: str) -> types.ModuleType:
        """Force-reload a module, bypassing the cache.

        The cached entry (if any) is invalidated and the module
        is re-imported from scratch.

        Args:
            module_path: Dotted module path to reload.

        Returns:
            The reloaded module.

        Raises:
            ImportError: If the module cannot be imported after
                invalidation.
            ValueError: If the module path is empty.
        """
        if not module_path:
            raise ValueError("Module path cannot be empty")

        with self._lock:
            if module_path in self._loaded_modules:
                del self._loaded_modules[module_path]
            if module_path in sys.modules:
                del sys.modules[module_path]
            self._stats["reloads"] += 1

        logger.debug("Force-reloading module '%s'.", module_path)
        return self.import_module(module_path)

    def get_stats(self) -> Dict[str, Any]:
        """Return importer statistics."""
        with self._lock:
            return {
                "imports": self._stats["imports"],
                "cache_hits": self._stats["cache_hits"],
                "errors": self._stats["errors"],
                "instances_created": self._stats["instances_created"],
                "reloads": self._stats["reloads"],
                "unloads": self._stats["unloads"],
                "cached_modules": len(self._loaded_modules),
            }

    def invalidate_all(self) -> None:
        """Clear all cached modules and statistics."""
        with self._lock:
            self._loaded_modules.clear()
            for key in list(self._stats.keys()):
                self._stats[key] = 0
        logger.debug("Invalidated all importer caches.")

    def _looks_like_plugin_class(self, obj: type) -> bool:
        """Heuristically determine whether a class is a plugin.

        Checks for the presence of common plugin method names.
        """
        for name in _PLUGIN_METHOD_HINTS:
            if hasattr(obj, name) and callable(getattr(obj, name)):
                return True
        return False

    def _import_from_file(self, file_path: str) -> types.ModuleType:
        """Import a module from a file path."""
        if not file_path:
            raise ImportError("File path cannot be empty")
        if not os.path.exists(file_path):
            raise ImportError(f"File does not exist: {file_path}")

        with self._lock:
            cached = self._loaded_modules.get(file_path)
            if cached is not None:
                self._stats["cache_hits"] += 1
                return cached

        module_name = os.path.splitext(os.path.basename(file_path))[0]
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None or spec.loader is None:
            raise ImportError(
                f"Could not create module spec for file: {file_path}"
            )
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception as exc:
            raise ImportError(
                f"Failed to execute module '{file_path}': {exc}"
            ) from exc

        with self._lock:
            self._loaded_modules[file_path] = module
            self._stats["imports"] += 1

        return module

    @staticmethod
    def _looks_like_file_path(value: str) -> bool:
        """Heuristically determine whether a string is a file path."""
        if not value:
            return False
        if value.endswith(".py"):
            return True
        if os.path.sep in value or "/" in value or "\\" in value:
            return True
        return os.path.exists(value)