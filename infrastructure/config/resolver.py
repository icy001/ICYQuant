"""
Configuration Resolver.

Resolves configuration from multiple sources
by loading each source, sorting by priority,
and merging the results.

Resolution Flow:
    1. Load all sources
    2. Filter unavailable sources
    3. Sort by priority (lowest first)
    4. Merge using ConfigurationMerger
    5. Validate merged configuration
    6. Return immutable snapshot
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .merger import ConfigurationMerger
from .snapshot import ConfigurationSnapshot

logger = logging.getLogger(__name__)


class ConfigurationResolver:
    """
    Resolves configuration from multiple sources.

    Loads all available sources, sorts by priority,
    and merges them into a single configuration.

    Usage:
        resolver = ConfigurationResolver()
        resolver.add_source(DefaultsSource())
        resolver.add_source(YAMLSource("config.yaml"))
        resolver.add_source(EnvironmentSource())
        resolver.add_source(CLISource())

        snapshot = await resolver.resolve()
    """

    def __init__(
        self,
        sources: Optional[List[Any]] = None,
        merger: Optional[ConfigurationMerger] = None,
    ) -> None:
        """
        Initialize resolver.

        Args:
            sources: List of configuration sources.
            merger: ConfigurationMerger instance.
        """
        self._sources: List[Any] = sources or []
        self._merger = merger or ConfigurationMerger()
        self._loaded_count: int = 0
        self._failed_count: int = 0

    @property
    def source_count(
        self,
    ) -> int:
        """Get number of registered sources."""
        return len(self._sources)

    @property
    def loaded_count(
        self,
    ) -> int:
        """Get number of successfully loaded sources."""
        return self._loaded_count

    @property
    def failed_count(
        self,
    ) -> int:
        """Get number of failed sources."""
        return self._failed_count

    def add_source(
        self,
        source: Any,
    ) -> None:
        """
        Add a configuration source.

        Args:
            source: ConfigurationSource instance.
        """
        self._sources.append(source)

    def add_sources(
        self,
        sources: List[Any],
    ) -> None:
        """Add multiple sources."""
        self._sources.extend(sources)

    def clear_sources(
        self,
    ) -> None:
        """Clear all sources."""
        self._sources.clear()

    async def resolve(
        self,
    ) -> ConfigurationSnapshot:
        """
        Resolve configuration from all sources.

        Steps:
        1. Sort sources by priority (lowest first)
        2. Load each available source
        3. Merge all configurations
        4. Create immutable snapshot

        Returns:
            ConfigurationSnapshot with merged values.
        """
        self._loaded_count = 0
        self._failed_count = 0

        # Sort sources by priority (lowest first)
        sorted_sources = sorted(
            self._sources,
            key=lambda s: s.priority,
        )

        # Load each source
        configs: List[Dict[str, Any]] = []
        sources_used: List[str] = []

        for source in sorted_sources:
            if not source.is_available():
                logger.debug(f"Skipping unavailable source: {source.name}")
                continue

            try:
                config = await source.async_load()
                if config:
                    configs.append(config)
                    sources_used.append(source.name)
                    self._loaded_count += 1
                    logger.debug(
                        f"Loaded {len(config)} keys from {source.name}"
                    )
            except Exception as e:
                self._failed_count += 1
                logger.warning(
                    f"Failed to load source {source.name}: {e}"
                )

        # Merge configurations
        merged = self._merger.merge(configs)

        # Create snapshot
        snapshot = ConfigurationSnapshot(
            values=merged,
            sources_used=sources_used,
        )

        logger.info(
            f"Resolved {len(merged)} config keys "
            f"from {self._loaded_count} sources"
        )

        return snapshot

    def get_status(
        self,
    ) -> Dict[str, Any]:
        """Get resolver status."""
        return {
            "sources": [
                {
                    "name": s.name,
                    "priority": s.priority,
                    "available": s.is_available(),
                }
                for s in self._sources
            ],
            "loaded_count": self._loaded_count,
            "failed_count": self._failed_count,
        }
