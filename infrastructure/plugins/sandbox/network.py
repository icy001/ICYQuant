"""Network access policy management.

Provides :class:`NetworkPolicy` for controlling network access
per plugin, with host allowlisting and protocol restrictions.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List

from ..exceptions import PluginNetworkAccessError

logger = logging.getLogger(__name__)


class NetworkPolicy:
    """Controls network access for sandboxed plugins.

    Each plugin has a configurable set of allowed network hosts
    and protocols.  Access checks verify both the allow-list and
    the protocol.

    Attributes:
        _allowed_hosts: Maps plugin_id to a list of allowed host patterns.
        _allowed_protocols: Maps plugin_id to a set of allowed protocols.
        _denied_hosts: Maps plugin_id to a set of denied host patterns.
        _lock: Thread-safe reentrant lock.
    """

    def __init__(self) -> None:
        self._allowed_hosts: Dict[str, List[str]] = {}
        self._allowed_protocols: Dict[str, set[str]] = {}
        self._denied_hosts: Dict[str, set[str]] = {}
        self._lock = threading.RLock()
        self._default_protocols = {"http", "https"}

    def allow_host(
        self, plugin_id: str, host_pattern: str, protocol: str = "https"
    ) -> None:
        """Allow network access to a host for a plugin.

        Args:
            plugin_id: Unique identifier for the plugin.
            host_pattern: Hostname or host pattern (supports wildcards).
            protocol: Protocol to allow (e.g. ``http``, ``https``).
        """
        with self._lock:
            if plugin_id not in self._allowed_hosts:
                self._allowed_hosts[plugin_id] = []
            self._allowed_hosts[plugin_id].append(host_pattern)

            if plugin_id not in self._allowed_protocols:
                self._allowed_protocols[plugin_id] = set(
                    self._default_protocols
                )
            self._allowed_protocols[plugin_id].add(protocol)

            logger.debug(
                "Allowed %s access to '%s' for plugin %s",
                protocol, host_pattern, plugin_id,
            )

    def deny_host(self, plugin_id: str, host_pattern: str) -> None:
        """Deny network access to a host for a plugin.

        Args:
            plugin_id: Unique identifier for the plugin.
            host_pattern: Hostname or host pattern to deny.
        """
        with self._lock:
            if plugin_id not in self._denied_hosts:
                self._denied_hosts[plugin_id] = set()
            self._denied_hosts[plugin_id].add(host_pattern)
            logger.debug(
                "Denied network access to '%s' for plugin %s",
                host_pattern, plugin_id,
            )

    def check_access(
        self,
        plugin_id: str,
        host: str,
        protocol: str = "https",
    ) -> bool:
        """Check whether a plugin has network access to a host.

        Args:
            plugin_id: Unique identifier for the plugin.
            host: The hostname to check.
            protocol: The protocol to check.

        Returns:
            True if access is granted, False otherwise.
        """
        with self._lock:
            denied = self._denied_hosts.get(plugin_id, set())
            for pattern in denied:
                if self._host_matches(host, pattern):
                    return False

            protocols = self._allowed_protocols.get(
                plugin_id, self._default_protocols
            )
            if protocol not in protocols:
                return False

            allowed = self._allowed_hosts.get(plugin_id, [])
            if not allowed:
                return False

            return any(
                self._host_matches(host, pattern) for pattern in allowed
            )

    def require_access(
        self,
        plugin_id: str,
        host: str,
        protocol: str = "https",
    ) -> None:
        """Require network access, raising if it is not granted.

        Args:
            plugin_id: Unique identifier for the plugin.
            host: The hostname to check.
            protocol: The protocol to check.

        Raises:
            PluginNetworkAccessError: If access is not granted.
        """
        if not self.check_access(plugin_id, host, protocol):
            raise PluginNetworkAccessError(
                f"Plugin '{plugin_id}' does not have {protocol} "
                f"network access to host: {host}"
            )

    def get_allowed_hosts(self, plugin_id: str) -> List[str]:
        """Get allowed host patterns for a plugin.

        Args:
            plugin_id: Unique identifier for the plugin.

        Returns:
            A list of allowed host patterns.
        """
        with self._lock:
            return list(self._allowed_hosts.get(plugin_id, []))

    def get_allowed_protocols(self, plugin_id: str) -> List[str]:
        """Get allowed protocols for a plugin.

        Args:
            plugin_id: Unique identifier for the plugin.

        Returns:
            A sorted list of allowed protocol strings.
        """
        with self._lock:
            protos = self._allowed_protocols.get(
                plugin_id, self._default_protocols
            )
            return sorted(protos)

    @staticmethod
    def _host_matches(host: str, pattern: str) -> bool:
        """Check whether a host matches a pattern.

        Supports wildcard matching: ``*.example.com`` matches
        ``api.example.com``.

        Args:
            host: The concrete hostname.
            pattern: The host pattern with optional wildcards.

        Returns:
            True if the host matches the pattern.
        """
        if host == pattern:
            return True
        if pattern.startswith("*."):
            suffix = pattern[1:]
            return host.endswith(suffix)
        return False

    def get_stats(self) -> Dict[str, Any]:
        """Get network policy statistics.

        Returns:
            A dictionary with ``total_plugins`` and per-plugin
            summaries.
        """
        with self._lock:
            plugins = []
            for pid in self._allowed_hosts:
                plugins.append({
                    "plugin_id": pid,
                    "allowed_hosts_count": len(
                        self._allowed_hosts.get(pid, [])
                    ),
                    "allowed_protocols": self.get_allowed_protocols(pid),
                    "denied_hosts_count": len(
                        self._denied_hosts.get(pid, set())
                    ),
                })
            return {
                "total_plugins": len(self._allowed_hosts),
                "plugins": plugins,
            }