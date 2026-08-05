"""Sandbox permission guard.

Provides :class:`SandboxPermissionGuard` for managing fine-grained
permissions granted to sandboxed plugins, with thread-safe
checking and audit capabilities.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List

from ..exceptions import PluginSandboxViolationError

logger = logging.getLogger(__name__)


class SandboxPermissionGuard:
    """Manages and enforces sandbox permissions per plugin.

    Each plugin is mapped to a set of allowed permission strings.
    All permission checks are thread-safe via an ``RLock``.

    Attributes:
        _permissions: Maps plugin_id to a set of permission strings.
        _denied: Maps plugin_id to a set of explicitly denied permissions.
        _audit_log: Accumulates audit entries for permission checks.
    """

    def __init__(self) -> None:
        self._permissions: Dict[str, set[str]] = {}
        self._denied: Dict[str, set[str]] = {}
        self._audit_log: List[Dict[str, Any]] = []
        self._lock = threading.RLock()
        self._max_audit_entries = 10000

    def grant_permission(self, plugin_id: str, permission: str) -> None:
        """Grant a permission to a plugin.

        Args:
            plugin_id: Unique identifier for the plugin.
            permission: The permission string to grant.
        """
        with self._lock:
            if plugin_id not in self._permissions:
                self._permissions[plugin_id] = set()
            self._permissions[plugin_id].add(permission)
            self._record_audit(plugin_id, "grant", permission, True)
            logger.debug(
                "Granted permission '%s' to plugin %s",
                permission, plugin_id,
            )

    def revoke_permission(self, plugin_id: str, permission: str) -> None:
        """Revoke a permission from a plugin.

        Args:
            plugin_id: Unique identifier for the plugin.
            permission: The permission string to revoke.
        """
        with self._lock:
            perms = self._permissions.get(plugin_id)
            if perms and permission in perms:
                perms.discard(permission)
                self._record_audit(plugin_id, "revoke", permission, True)
                logger.debug(
                    "Revoked permission '%s' from plugin %s",
                    permission, plugin_id,
                )

    def check_permission(self, plugin_id: str, permission: str) -> bool:
        """Check whether a plugin holds a specific permission.

        Args:
            plugin_id: Unique identifier for the plugin.
            permission: The permission string to check.

        Returns:
            True if the permission is granted, False otherwise.
        """
        with self._lock:
            denied = self._denied.get(plugin_id, set())
            if permission in denied:
                self._record_audit(plugin_id, "check", permission, False)
                return False
            perms = self._permissions.get(plugin_id, set())
            granted = permission in perms
            self._record_audit(plugin_id, "check", permission, granted)
            return granted

    def require_permission(self, plugin_id: str, permission: str) -> None:
        """Require a permission, raising if it is not granted.

        Args:
            plugin_id: Unique identifier for the plugin.
            permission: The permission string to require.

        Raises:
            PluginSandboxViolationError: If the permission is not granted.
        """
        if not self.check_permission(plugin_id, permission):
            raise PluginSandboxViolationError(
                f"Plugin '{plugin_id}' requires permission '{permission}' "
                f"but it is not granted"
            )

    def get_permissions(self, plugin_id: str) -> List[str]:
        """Get all permissions granted to a plugin.

        Args:
            plugin_id: Unique identifier for the plugin.

        Returns:
            A sorted list of permission strings.
        """
        with self._lock:
            perms = self._permissions.get(plugin_id, set())
            return sorted(perms)

    def set_permissions(self, plugin_id: str, permissions: List[str]) -> None:
        """Set the complete permission set for a plugin.

        Replaces any existing permissions with the provided list.

        Args:
            plugin_id: Unique identifier for the plugin.
            permissions: List of permission strings to grant.
        """
        with self._lock:
            self._permissions[plugin_id] = set(permissions)
            for perm in permissions:
                self._record_audit(plugin_id, "set", perm, True)
            logger.debug(
                "Set %d permissions for plugin %s",
                len(permissions), plugin_id,
            )

    def clear_permissions(self, plugin_id: str) -> None:
        """Clear all permissions for a plugin.

        Args:
            plugin_id: Unique identifier for the plugin.
        """
        with self._lock:
            self._permissions.pop(plugin_id, None)
            self._denied.pop(plugin_id, None)
            self._record_audit(plugin_id, "clear", "*", True)
            logger.debug("Cleared all permissions for plugin %s", plugin_id)

    def audit_permissions(self, plugin_id: str) -> Dict[str, Any]:
        """Get a permission audit summary for a plugin.

        Args:
            plugin_id: Unique identifier for the plugin.

        Returns:
            A dictionary with ``plugin_id``, ``permissions``,
            ``denied``, ``total_checks``, and ``recent_checks``.
        """
        with self._lock:
            perms = self._permissions.get(plugin_id, set())
            denied = self._denied.get(plugin_id, set())
            recent = [
                entry for entry in self._audit_log
                if entry.get("plugin_id") == plugin_id
            ]
            return {
                "plugin_id": plugin_id,
                "permissions": sorted(perms),
                "denied": sorted(denied),
                "total_checks": len(recent),
                "recent_checks": recent[-10:],
            }

    def _record_audit(
        self, plugin_id: str, action: str, permission: str, result: bool
    ) -> None:
        """Record an audit entry (must be called with lock held).

        Args:
            plugin_id: The plugin involved.
            action: The action performed.
            permission: The permission string involved.
            result: Whether the action was allowed.
        """
        entry: Dict[str, Any] = {
            "plugin_id": plugin_id,
            "action": action,
            "permission": permission,
            "result": result,
        }
        self._audit_log.append(entry)
        if len(self._audit_log) > self._max_audit_entries:
            self._audit_log = self._audit_log[-self._max_audit_entries:]

    def get_stats(self) -> Dict[str, Any]:
        """Get permission guard statistics.

        Returns:
            A dictionary with ``total_plugins``, ``total_permissions``,
            ``audit_entries``, and ``plugins`` (per-plugin summary).
        """
        with self._lock:
            total_perms = sum(len(p) for p in self._permissions.values())
            plugins = []
            for pid, perms in self._permissions.items():
                plugins.append({
                    "plugin_id": pid,
                    "permissions_count": len(perms),
                    "permissions": sorted(perms),
                })
            return {
                "total_plugins": len(self._permissions),
                "total_permissions": total_perms,
                "audit_entries": len(self._audit_log),
                "plugins": plugins,
            }