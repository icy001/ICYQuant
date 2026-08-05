"""Trust store for plugin verification.

Provides :class:`TrustStore` for managing trust decisions
for plugins, with support for public key storage, JSON
persistence, and thread-safe operations.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional

from ..exceptions import PluginTrustError

logger = logging.getLogger(__name__)


class TrustStore:
    """Manages trust decisions for plugins.

    Plugins must be added to the trust store before they
    can be loaded and executed in a sandbox.  Each trust
    decision is recorded with a timestamp and optional
    metadata.  The trust store supports JSON persistence
    for import/export operations.

    Attributes:
        _trusted: Maps plugin_id to trust metadata dict.
        _public_keys: Maps plugin_id to public key string.
        _lock: Thread-safe reentrant lock.
    """

    def __init__(self) -> None:
        self._trusted: Dict[str, Dict[str, Any]] = {}
        self._public_keys: Dict[str, str] = {}
        self._lock = threading.RLock()

    def trust(
        self,
        plugin_id: str,
        public_key: Optional[str] = None,
    ) -> None:
        """Add a plugin to the trust store.

        Args:
            plugin_id: Unique identifier for the plugin.
            public_key: Optional public key to associate.
        """
        with self._lock:
            self._trusted[plugin_id] = {
                "trusted_at": time.time(),
                "trusted": True,
            }
            if public_key:
                self._public_keys[plugin_id] = public_key
            logger.info(
                "Added plugin %s to trust store", plugin_id
            )

    def distrust(self, plugin_id: str) -> None:
        """Remove a plugin from the trust store.

        Args:
            plugin_id: Unique identifier for the plugin.
        """
        with self._lock:
            self._trusted.pop(plugin_id, None)
            self._public_keys.pop(plugin_id, None)
            logger.info(
                "Removed plugin %s from trust store", plugin_id
            )

    def is_trusted(self, plugin_id: str) -> bool:
        """Check whether a plugin is trusted.

        Args:
            plugin_id: Unique identifier for the plugin.

        Returns:
            True if the plugin is in the trust store.
        """
        with self._lock:
            return plugin_id in self._trusted

    def require_trusted(self, plugin_id: str) -> None:
        """Require trust, raising if not trusted.

        Args:
            plugin_id: Unique identifier for the plugin.

        Raises:
            PluginTrustError: If the plugin is not trusted.
        """
        if not self.is_trusted(plugin_id):
            raise PluginTrustError(
                f"Plugin '{plugin_id}' is not in the trust store"
            )

    def get_trusted(self) -> List[Dict[str, Any]]:
        """Get the list of trusted plugins with metadata.

        Returns:
            A list of dictionaries with ``plugin_id``,
            ``trusted_at``, and any associated metadata.
        """
        with self._lock:
            result = []
            for pid, info in self._trusted.items():
                entry: Dict[str, Any] = {
                    "plugin_id": pid,
                    "trusted_at": info.get("trusted_at"),
                    "trusted": info.get("trusted", True),
                }
                if pid in self._public_keys:
                    entry["has_public_key"] = True
                result.append(entry)
            return sorted(result, key=lambda x: x["plugin_id"])

    def add_public_key(
        self, plugin_id: str, public_key: str
    ) -> None:
        """Add a public key for a trusted plugin.

        Args:
            plugin_id: Unique identifier for the plugin.
            public_key: The PEM-encoded public key string.
        """
        with self._lock:
            self._public_keys[plugin_id] = public_key
            logger.debug(
                "Added public key for plugin %s", plugin_id
            )

    def get_public_key(self, plugin_id: str) -> Optional[str]:
        """Get the public key for a trusted plugin.

        Args:
            plugin_id: Unique identifier for the plugin.

        Returns:
            The PEM-encoded public key string, or None if not
            available.
        """
        with self._lock:
            return self._public_keys.get(plugin_id)

    def import_truststore(self, path: str) -> None:
        """Import a trust store from a JSON file.

        Overwrites the current trust store with the imported
        data.

        Args:
            path: Filesystem path to the JSON trust store file.

        Raises:
            PluginTrustError: If the file cannot be read or parsed.
        """
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)

            trusted = data.get("trusted", {})
            public_keys = data.get("public_keys", {})

            with self._lock:
                self._trusted = {
                    pid: info
                    for pid, info in trusted.items()
                }
                self._public_keys = {
                    pid: key
                    for pid, key in public_keys.items()
                }

            logger.info(
                "Imported trust store from %s (%d trusted, %d keys)",
                path,
                len(self._trusted),
                len(self._public_keys),
            )
        except (IOError, OSError, json.JSONDecodeError) as exc:
            raise PluginTrustError(
                f"Failed to import trust store from '{path}': {exc}"
            ) from exc

    def export_truststore(self, path: str) -> None:
        """Export the trust store to a JSON file.

        Args:
            path: Filesystem path to write the JSON trust store.

        Raises:
            PluginTrustError: If the file cannot be written.
        """
        try:
            with self._lock:
                data = {
                    "trusted": dict(self._trusted),
                    "public_keys": dict(self._public_keys),
                    "exported_at": time.time(),
                }

            os.makedirs(
                os.path.dirname(path) or ".", exist_ok=True
            )
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, sort_keys=True)

            logger.info(
                "Exported trust store to %s", path
            )
        except (IOError, OSError) as exc:
            raise PluginTrustError(
                f"Failed to export trust store to '{path}': {exc}"
            ) from exc

    def clear(self) -> None:
        """Remove all plugins from the trust store."""
        with self._lock:
            self._trusted.clear()
            self._public_keys.clear()
            logger.info("Cleared trust store")

    def get_stats(self) -> Dict[str, Any]:
        """Get trust store statistics.

        Returns:
            A dictionary with trusted count, key count, and
            plugin list.
        """
        with self._lock:
            return {
                "total_trusted": len(self._trusted),
                "total_public_keys": len(self._public_keys),
                "plugins": sorted(self._trusted.keys()),
            }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the trust store to a dictionary.

        Returns:
            A dictionary with trusted plugins and public keys.
        """
        with self._lock:
            return {
                "trusted": dict(self._trusted),
                "public_keys": dict(self._public_keys),
            }