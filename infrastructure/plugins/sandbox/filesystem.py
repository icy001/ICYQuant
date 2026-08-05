"""Filesystem isolation policy.

Provides :class:`FilesystemPolicy` for controlling filesystem
access per plugin, with root-based path isolation and
read/write/execute permission checks.
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any, Dict, List

from ..exceptions import PluginFilesystemAccessError

logger = logging.getLogger(__name__)


class FilesystemPolicy:
    """Controls filesystem access for sandboxed plugins.

    Each plugin has a configurable root directory and a set of
    allowed paths with specific access levels (``read``, ``write``,
    or ``execute``).  Access checks verify both the explicit
    allow-list and that the requested path is within the plugin's
    root directory.

    Attributes:
        _roots: Maps plugin_id to the filesystem root path.
        _allowed_paths: Maps plugin_id to a dict of path → list of
            allowed access modes.
        _denied_paths: Maps plugin_id to a set of denied paths.
        _lock: Thread-safe reentrant lock.
    """

    def __init__(self) -> None:
        self._roots: Dict[str, str] = {}
        self._allowed_paths: Dict[str, Dict[str, set[str]]] = {}
        self._denied_paths: Dict[str, set[str]] = {}
        self._lock = threading.RLock()

    def allow_path(
        self, plugin_id: str, path: str, access: str = "read"
    ) -> None:
        """Allow access to a path for a plugin.

        Args:
            plugin_id: Unique identifier for the plugin.
            path: The filesystem path to allow.
            access: Access mode (``read``, ``write``, or ``execute``).
        """
        normalized = os.path.normpath(path)
        with self._lock:
            if plugin_id not in self._allowed_paths:
                self._allowed_paths[plugin_id] = {}
            path_perms = self._allowed_paths[plugin_id]
            if normalized not in path_perms:
                path_perms[normalized] = set()
            path_perms[normalized].add(access)
            logger.debug(
                "Allowed %s access to '%s' for plugin %s",
                access, normalized, plugin_id,
            )

    def deny_path(self, plugin_id: str, path: str) -> None:
        """Deny access to a path for a plugin.

        Denied paths take precedence over allowed paths.

        Args:
            plugin_id: Unique identifier for the plugin.
            path: The filesystem path to deny.
        """
        normalized = os.path.normpath(path)
        with self._lock:
            if plugin_id not in self._denied_paths:
                self._denied_paths[plugin_id] = set()
            self._denied_paths[plugin_id].add(normalized)
            logger.debug(
                "Denied access to '%s' for plugin %s",
                normalized, plugin_id,
            )

    def check_access(
        self, plugin_id: str, path: str, access: str = "read"
    ) -> bool:
        """Check whether a plugin has access to a path.

        Args:
            plugin_id: Unique identifier for the plugin.
            path: The filesystem path to check.
            access: Access mode (``read``, ``write``, or ``execute``).

        Returns:
            True if access is granted, False otherwise.
        """
        normalized = os.path.normpath(path)
        with self._lock:
            denied = self._denied_paths.get(plugin_id, set())
            if normalized in denied:
                return False

            if not self.is_within_root(plugin_id, path):
                return False

            allowed = self._allowed_paths.get(plugin_id, {})
            for allowed_path, modes in allowed.items():
                if self._path_matches(normalized, allowed_path):
                    if access in modes or "all" in modes:
                        return True

            return False

    def require_access(
        self, plugin_id: str, path: str, access: str = "read"
    ) -> None:
        """Require access to a path, raising if it is not granted.

        Args:
            plugin_id: Unique identifier for the plugin.
            path: The filesystem path to check.
            access: Access mode (``read``, ``write``, or ``execute``).

        Raises:
            PluginFilesystemAccessError: If access is not granted.
        """
        if not self.check_access(plugin_id, path, access):
            raise PluginFilesystemAccessError(
                f"Plugin '{plugin_id}' does not have {access} access "
                f"to path: {path}"
            )

    def get_allowed_paths(
        self, plugin_id: str
    ) -> Dict[str, List[str]]:
        """Get all allowed paths and their access modes for a plugin.

        Args:
            plugin_id: Unique identifier for the plugin.

        Returns:
            A dictionary mapping path to a list of allowed access modes.
        """
        with self._lock:
            allowed = self._allowed_paths.get(plugin_id, {})
            return {
                path: sorted(modes) for path, modes in allowed.items()
            }

    def set_root(self, plugin_id: str, root_path: str) -> None:
        """Set the filesystem root for a plugin.

        The plugin may only access paths under this root directory.

        Args:
            plugin_id: Unique identifier for the plugin.
            root_path: The absolute path to the plugin's root directory.
        """
        normalized = os.path.normpath(root_path)
        with self._lock:
            self._roots[plugin_id] = normalized
            logger.info(
                "Set filesystem root '%s' for plugin %s",
                normalized, plugin_id,
            )

    def is_within_root(self, plugin_id: str, path: str) -> bool:
        """Check whether a path is within the plugin's root directory.

        Args:
            plugin_id: Unique identifier for the plugin.
            path: The filesystem path to check.

        Returns:
            True if the path is under the root, or if no root is set.
        """
        with self._lock:
            root = self._roots.get(plugin_id)
            if root is None:
                return True
            normalized = os.path.normpath(path)
            if normalized == root:
                return True
            return normalized.startswith(root + os.sep)

    @staticmethod
    def _path_matches(path: str, pattern: str) -> bool:
        """Check whether a path matches an allowed path pattern.

        Supports prefix matching: if the allowed path is a directory,
        all files under it are matched.

        Args:
            path: The concrete path to check.
            pattern: The allowed path pattern.

        Returns:
            True if the path matches the pattern.
        """
        if path == pattern:
            return True
        if pattern.endswith(os.sep) or os.path.isdir(pattern):
            return path.startswith(pattern + os.sep)
        return False

    def get_stats(self) -> Dict[str, Any]:
        """Get filesystem policy statistics.

        Returns:
            A dictionary with ``total_plugins``, ``plugins``
            (per-plugin summary), and ``roots``.
        """
        with self._lock:
            plugins = []
            for pid in self._allowed_paths:
                allowed = self._allowed_paths.get(pid, {})
                denied = self._denied_paths.get(pid, set())
                plugins.append({
                    "plugin_id": pid,
                    "root": self._roots.get(pid),
                    "allowed_paths_count": len(allowed),
                    "denied_paths_count": len(denied),
                })
            return {
                "total_plugins": len(self._allowed_paths),
                "plugins": plugins,
                "roots": dict(self._roots),
            }