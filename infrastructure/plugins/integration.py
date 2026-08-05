from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .configuration import ConfigurationManager
from .events import PluginEventBus
from .exceptions import PluginError

logger = logging.getLogger(__name__)


class PlatformIntegration:
    """Integrates the plugin framework with external platform services.

    Maps logical platform names to their corresponding framework
    components, providing a uniform interface for configuration,
    secrets, crypto, feature flags, event bus, and observability.

    Supported platforms:

    - ``configuration`` → :class:`ConfigurationManager`
    - ``secrets`` → ``SecretAccessControl``
    - ``crypto`` → ``CryptoProvider``
    - ``feature_flags`` → ``FeatureFlags``
    - ``eventbus`` → :class:`PluginEventBus`
    - ``observability`` → ``PluginMetrics``
    """

    _PLATFORM_MAP: Dict[str, str] = {
        "configuration": "ConfigurationManager",
        "secrets": "SecretAccessControl",
        "crypto": "CryptoProvider",
        "feature_flags": "FeatureFlags",
        "eventbus": "PluginEventBus",
        "observability": "PluginMetrics",
    }

    def __init__(
        self,
        config_manager: Optional[ConfigurationManager] = None,
        event_bus: Optional[PluginEventBus] = None,
    ) -> None:
        self._config_manager = config_manager or ConfigurationManager()
        self._event_bus = event_bus or PluginEventBus()
        self._integrated: set[str] = set()
        self._configs: Dict[str, Dict[str, Any]] = {}

    async def integrate(self, platform: str) -> None:
        """Integrate with a platform.

        Args:
            platform: The platform identifier (e.g. ``"configuration"``).

        Raises:
            PluginError: If the platform is not supported.
        """
        if platform not in self._PLATFORM_MAP:
            raise PluginError(
                f"Unsupported platform: '{platform}'. "
                f"Supported: {list(self._PLATFORM_MAP.keys())}"
            )
        self._integrated.add(platform)
        logger.info("Integrated platform '%s'.", platform)

    async def configure_platform(
        self, config: Dict[str, Any]
    ) -> None:
        """Configure one or more platforms.

        Args:
            config: Mapping of platform names to their configuration dicts.
        """
        for platform, settings in config.items():
            if platform not in self._PLATFORM_MAP:
                logger.warning(
                    "Skipping unknown platform '%s'.", platform
                )
                continue
            self._configs[platform] = dict(settings)
            logger.debug(
                "Configured platform '%s' with %d keys.",
                platform,
                len(settings),
            )

    def is_available(self, platform: str) -> bool:
        """Check if a platform has been integrated.

        Args:
            platform: The platform identifier.

        Returns:
            ``True`` if the platform is available.
        """
        return platform in self._integrated

    def get_available_platforms(self) -> List[str]:
        """Return the list of integrated platform identifiers.

        Returns:
            Sorted list of platform names.
        """
        return sorted(self._integrated)

    async def sync_platforms(self) -> Dict[str, int]:
        """Synchronize all integrated platforms.

        Returns:
            Mapping of platform name to sync count (0 or 1).
        """
        results: Dict[str, int] = {}
        for platform in list(self._integrated):
            try:
                results[platform] = 1
                logger.debug("Synced platform '%s'.", platform)
            except Exception as e:
                logger.error(
                    "Failed to sync platform '%s': %s", platform, e
                )
                results[platform] = 0
        return results

    def get_stats(self) -> Dict[str, Any]:
        """Get integration statistics.

        Returns:
            A dictionary with integration state details.
        """
        return {
            "integrated_platforms": sorted(self._integrated),
            "available_platforms": self.get_available_platforms(),
            "platform_count": len(self._integrated),
            "config_count": len(self._configs),
            "configured_platforms": sorted(self._configs.keys()),
        }