"""
Strategy factory for creating strategy instances.

Creates, configures, and assembles strategy instances from manifests,
templates, or programmatic definitions.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .strategy_manifest import StrategyManifest
from .strategy_template import StrategyTemplate
from .strategy_version import StrategyVersion

logger = logging.getLogger(__name__)


class StrategyFactory:
    """Factory for creating and assembling strategy instances.

    Supports creation from:
        - Manifests (loaded from packages)
        - Templates (pre-configured blueprints)
        - Programmatic definitions (code-based configuration)
    """

    def __init__(self) -> None:
        self._initialized: bool = False

    # ── Lifecycle ──

    async def initialize(self) -> None:
        self._initialized = True
        logger.info("StrategyFactory initialized")

    async def shutdown(self) -> None:
        self._initialized = False
        logger.info("StrategyFactory shut down")

    # ── Creation Methods ──

    def create_from_manifest(
        self,
        manifest: StrategyManifest,
        strategy_id: Optional[str] = None,
        config_overrides: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a strategy definition from a manifest.

        Returns a strategy descriptor dict that can be used by the
        StrategyRegistry for registration.
        """
        strategy_id = strategy_id or f"{manifest.name}_{manifest.version}"

        config = {}
        if manifest.config_schema and "properties" in manifest.config_schema:
            for key, prop in manifest.config_schema["properties"].items():
                if "default" in prop:
                    config[key] = prop["default"]

        if config_overrides:
            config.update(config_overrides)

        return {
            "strategy_id": strategy_id,
            "manifest": manifest,
            "config": config,
            "entry_point": manifest.entry_point,
            "capability": manifest.capability,
        }

    def create_from_template(
        self,
        template: StrategyTemplate,
        strategy_name: str,
        version: str = "0.1.0",
        author: str = "unknown",
        config_overrides: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Create a strategy from a template.

        Args:
            template: The template blueprint.
            strategy_name: Name for the new strategy.
            version: Initial version string.
            author: Strategy author.
            config_overrides: Override default configuration values.
            **kwargs: Additional overrides for the manifest.

        Returns:
            A strategy descriptor dict ready for registration.
        """
        manifest = template.create_manifest(
            strategy_name=strategy_name,
            version=version,
            author=author,
            **kwargs,
        )

        return self.create_from_manifest(
            manifest=manifest,
            config_overrides=config_overrides,
        )

    def create_from_definition(
        self,
        name: str,
        version: str,
        entry_module: str,
        config: Optional[Dict[str, Any]] = None,
        author: str = "unknown",
        description: str = "",
        tags: Optional[List[str]] = None,
        **capability_kwargs: Any,
    ) -> Dict[str, Any]:
        """Create a strategy from a programmatic definition."""
        from .strategy_manifest import (
            StrategyCapability,
            StrategyEntryPoint,
            StrategyManifest,
        )

        capability = StrategyCapability(**capability_kwargs)
        entry_point = StrategyEntryPoint(module=entry_module)

        manifest = StrategyManifest(
            name=name,
            version=version,
            author=author,
            description=description,
            capability=capability,
            entry_point=entry_point,
            tags=tags or [],
        )

        return self.create_from_manifest(
            manifest=manifest,
            config_overrides=config,
        )

    def generate_strategy_id(self, name: str, version: str) -> str:
        """Generate a unique strategy identifier."""
        import uuid

        short_id = uuid.uuid4().hex[:8]
        return f"{name}-{version}-{short_id}"
