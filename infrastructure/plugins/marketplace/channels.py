"""Release channel management for the plugin marketplace.

Provides :class:`MarketplaceChannels` for managing release channels
(stable, beta, dev) and channel-based plugin distribution.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_CHANNELS: Dict[str, Dict[str, Any]] = {
    "stable": {
        "name": "stable",
        "min_version": None,
        "update_interval": 86400,
        "auto_update": True,
        "description": "Production-ready releases.",
    },
    "beta": {
        "name": "beta",
        "min_version": None,
        "update_interval": 43200,
        "auto_update": False,
        "description": "Pre-release beta builds.",
    },
    "dev": {
        "name": "dev",
        "min_version": None,
        "update_interval": 3600,
        "auto_update": False,
        "description": "Development builds; may be unstable.",
    },
}


class MarketplaceChannels:
    """Manages release channels for plugin distribution.

    Default channels are ``stable``, ``beta``, and ``dev``. Each
    channel has a configuration with ``min_version``,
    ``update_interval``, and ``auto_update`` settings.

    Plugins can be pinned to a specific channel, and the system
    can retrieve all packages available in a channel.

    Usage::

        channels = MarketplaceChannels()
        channels.set_channel("my.plugin", "beta")
        pkgs = channels.get_channel_packages("stable")
    """

    def __init__(self) -> None:
        self._channels: Dict[str, Dict[str, Any]] = dict(
            DEFAULT_CHANNELS
        )
        self._plugin_channels: Dict[str, str] = {}
        self._channel_packages: Dict[str, List[Dict[str, Any]]] = {
            ch: [] for ch in self._channels
        }
        self._channel_count: int = 0

    def get_channel(self, name: str) -> Dict[str, Any]:
        """Get channel configuration by name.

        Args:
            name: Channel name (e.g. ``"stable"``, ``"beta"``).

        Returns:
            A dictionary with channel configuration, or an empty
            dict if the channel is not found.
        """
        return dict(self._channels.get(name, {}))

    def list_channels(self) -> List[Dict[str, Any]]:
        """List all configured channels.

        Returns:
            A list of channel configuration dictionaries.
        """
        return [dict(ch) for ch in self._channels.values()]

    def set_channel(self, plugin_id: str, channel: str) -> None:
        """Pin a plugin to a specific channel.

        Args:
            plugin_id: The plugin identifier.
            channel: Channel name to pin to.

        Raises:
            ValueError: If the channel does not exist.
        """
        if channel not in self._channels:
            raise ValueError(
                f"Unknown channel '{channel}'. "
                f"Available: {', '.join(sorted(self._channels))}"
            )

        self._plugin_channels[plugin_id] = channel
        self._channel_count += 1
        logger.info(
            "Set channel '%s' for plugin '%s'.", channel, plugin_id
        )

    def get_channel_for(self, plugin_id: str) -> str:
        """Get the pinned channel for a plugin.

        Args:
            plugin_id: The plugin identifier.

        Returns:
            The channel name, defaults to ``"stable"`` if not pinned.
        """
        return self._plugin_channels.get(plugin_id, "stable")

    def get_channel_packages(
        self, channel: str
    ) -> List[Dict[str, Any]]:
        """Get all packages available in a channel.

        Args:
            channel: Channel name.

        Returns:
            A list of package metadata dictionaries.
        """
        return list(self._channel_packages.get(channel, []))

    def add_channel(
        self, name: str, config: Dict[str, Any]
    ) -> None:
        """Add a new custom channel.

        Args:
            name: Channel name.
            config: Channel configuration dictionary with optional
                ``min_version``, ``update_interval``, ``auto_update``,
                and ``description`` keys.
        """
        self._channels[name] = {
            "name": name,
            "min_version": config.get("min_version"),
            "update_interval": config.get("update_interval", 86400),
            "auto_update": config.get("auto_update", False),
            "description": config.get("description", ""),
        }
        if name not in self._channel_packages:
            self._channel_packages[name] = []
        logger.info("Added channel '%s'.", name)

    def get_stats(self) -> Dict[str, Any]:
        """Return channel statistics.

        Returns:
            Dictionary with channel counts and plugin associations.
        """
        return {
            "total_channels": len(self._channels),
            "channel_names": sorted(self._channels.keys()),
            "pinned_plugins": len(self._plugin_channels),
            "channel_operations": self._channel_count,
            "packages_per_channel": {
                ch: len(pkgs)
                for ch, pkgs in self._channel_packages.items()
            },
        }