"""Secret access control.

Provides :class:`SecretAccessControl` for managing and auditing
access to secrets within sandboxed plugins, ensuring that only
authorized plugins can retrieve sensitive values.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List

from ..exceptions import PluginSecretAccessError

logger = logging.getLogger(__name__)


class SecretAccessControl:
    """Controls secret access for sandboxed plugins.

    Manages which plugins may access which secrets and records
    all access attempts for auditing.

    Attributes:
        _allowed_secrets: Maps plugin_id to a set of allowed secret keys.
        _denied_secrets: Maps plugin_id to a set of explicitly denied keys.
        _access_log: Accumulates access attempt entries.
        _lock: Thread-safe reentrant lock.
    """

    def __init__(self) -> None:
        self._allowed_secrets: Dict[str, set[str]] = {}
        self._denied_secrets: Dict[str, set[str]] = {}
        self._access_log: List[Dict[str, Any]] = []
        self._lock = threading.RLock()
        self._max_log_entries = 10000

    def grant_secret_access(
        self, plugin_id: str, secret_key: str
    ) -> None:
        """Grant a plugin access to a specific secret.

        Args:
            plugin_id: Unique identifier for the plugin.
            secret_key: The key identifying the secret.
        """
        with self._lock:
            if plugin_id not in self._allowed_secrets:
                self._allowed_secrets[plugin_id] = set()
            self._allowed_secrets[plugin_id].add(secret_key)
            logger.debug(
                "Granted secret access '%s' to plugin %s",
                secret_key, plugin_id,
            )

    def revoke_secret_access(
        self, plugin_id: str, secret_key: str
    ) -> None:
        """Revoke a plugin's access to a specific secret.

        Args:
            plugin_id: Unique identifier for the plugin.
            secret_key: The key identifying the secret.
        """
        with self._lock:
            secrets = self._allowed_secrets.get(plugin_id)
            if secrets and secret_key in secrets:
                secrets.discard(secret_key)
                logger.debug(
                    "Revoked secret access '%s' from plugin %s",
                    secret_key, plugin_id,
                )

    def check_secret_access(
        self, plugin_id: str, secret_key: str
    ) -> bool:
        """Check whether a plugin may access a secret.

        Args:
            plugin_id: Unique identifier for the plugin.
            secret_key: The key identifying the secret.

        Returns:
            True if access is granted, False otherwise.
        """
        with self._lock:
            denied = self._denied_secrets.get(plugin_id, set())
            if secret_key in denied:
                self._record_access(plugin_id, secret_key, False)
                return False
            secrets = self._allowed_secrets.get(plugin_id, set())
            granted = secret_key in secrets
            self._record_access(plugin_id, secret_key, granted)
            return granted

    def require_secret_access(
        self, plugin_id: str, secret_key: str
    ) -> None:
        """Require secret access, raising if not granted.

        Args:
            plugin_id: Unique identifier for the plugin.
            secret_key: The key identifying the secret.

        Raises:
            PluginSecretAccessError: If access is not granted.
        """
        if not self.check_secret_access(plugin_id, secret_key):
            raise PluginSecretAccessError(
                f"Plugin '{plugin_id}' is not authorized to access "
                f"secret: {secret_key}"
            )

    def get_allowed_secrets(self, plugin_id: str) -> List[str]:
        """Get the list of secrets a plugin may access.

        Args:
            plugin_id: Unique identifier for the plugin.

        Returns:
            A sorted list of secret keys.
        """
        with self._lock:
            secrets = self._allowed_secrets.get(plugin_id, set())
            return sorted(secrets)

    def _record_access(
        self, plugin_id: str, secret_key: str, granted: bool
    ) -> None:
        """Record a secret access attempt (must be called with lock held).

        Args:
            plugin_id: The plugin involved.
            secret_key: The secret key.
            granted: Whether access was granted.
        """
        entry: Dict[str, Any] = {
            "plugin_id": plugin_id,
            "secret_key": secret_key,
            "granted": granted,
        }
        self._access_log.append(entry)
        if len(self._access_log) > self._max_log_entries:
            self._access_log = self._access_log[-self._max_log_entries:]

    def get_stats(self) -> Dict[str, Any]:
        """Get secret access control statistics.

        Returns:
            A dictionary with ``total_plugins``, ``total_secrets_granted``,
            and per-plugin summaries.
        """
        with self._lock:
            total = sum(
                len(s) for s in self._allowed_secrets.values()
            )
            plugins = []
            for pid, secrets in self._allowed_secrets.items():
                plugins.append({
                    "plugin_id": pid,
                    "secrets_count": len(secrets),
                    "secrets": sorted(secrets),
                })
            return {
                "total_plugins": len(self._allowed_secrets),
                "total_secrets_granted": total,
                "access_log_entries": len(self._access_log),
                "plugins": plugins,
            }