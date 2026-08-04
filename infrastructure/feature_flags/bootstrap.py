"""
Feature flag platform bootstrap.

Provides the main bootstrap class that
initializes and starts the complete
feature flag platform production stack.

Bootstrap Flow:
    Configuration → Registry → Targeting → Rollout
        → Canary → Experiment → Runtime → Scheduler

This is the production entry point for
ICYQuant's feature flag platform.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from .config import FeatureFlagConfig
from .constants import EvaluationStrategy, FeatureFlagType
from .container import ServiceContainer
from .events import EventBus, FeatureEvent, FeatureEventType
from .hotreload import HotReloadManager
from .integration import PlatformIntegration
from .lifecycle import PlatformLifecycle
from .manager import FeatureFlagManager
from .monitoring import FeatureFlagRuntimeMetrics
from .protection import PlatformProtection
from .recovery import RecoveryManager
from .registry import FeatureRegistry
from .runtime import RuntimeFeatureService
from .scheduler import FeatureFlagScheduler
from .snapshot import FeatureSnapshot, SnapshotManager
from .telemetry import FeatureFlagTelemetry

logger = logging.getLogger(__name__)


class FeatureFlagBootstrap:
    """
    Production bootstrap for the feature flag platform.

    Handles the complete initialization sequence
    and provides a simple API for starting and
    stopping the platform.

    Bootstrap Sequence:
        1. Configuration Platform (config)
        2. Feature Registry (registry)
        3. Targeting Engine (targeting)
        4. Rollout Engine (rollout)
        5. Canary Engine (canary)
        6. Experiment Engine (experiment)
        7. Runtime Service (runtime)
        8. Scheduler (scheduler)

    Usage:
        bootstrap = FeatureFlagBootstrap(config)
        platform = await bootstrap.start()

        # Use the platform
        if platform.is_enabled("trading.new_risk"):
            ...

        await bootstrap.shutdown()
    """

    def __init__(
        self,
        config: Optional[FeatureFlagConfig] = None,
    ) -> None:
        """
        Initialize bootstrap with configuration.

        Args:
            config: Platform configuration.
        """
        self._config = config or FeatureFlagConfig()
        self._integration = PlatformIntegration()
        self._started = False

    @property
    def integration(self) -> PlatformIntegration:
        """Get the platform integration."""
        return self._integration

    @property
    def is_started(self) -> bool:
        """Check if the platform is started."""
        return self._started

    async def start(self) -> PlatformIntegration:
        """
        Bootstrap and start the entire platform.

        Returns:
            The PlatformIntegration instance.
        """
        if self._started:
            return self._integration

        logger.info(
            "Bootstrapping ICYQuant Feature Flag Platform v0.4.0-alpha2",
        )

        # Step 1: Configuration
        logger.info("  [1/8] Initializing configuration...")

        # Step 2: Feature Registry
        logger.info("  [2/8] Initializing feature registry...")

        # Step 3: Targeting Engine
        logger.info("  [3/8] Initializing targeting engine...")

        # Step 4: Rollout Engine
        logger.info("  [4/8] Initializing rollout engine...")

        # Step 5: Canary Engine
        logger.info("  [5/8] Initializing canary engine...")

        # Step 6: Experiment Engine
        logger.info("  [6/8] Initializing experiment engine...")

        # Step 7: Runtime Service
        logger.info("  [7/8] Initializing runtime service...")

        # Step 8: Start Platform
        logger.info("  [8/8] Starting platform...")
        await self._integration.start()

        self._started = True

        logger.info(
            "Feature Flag Platform started successfully "
            "(flags=%d, snapshot=v%d)",
            self._integration.runtime.get_stats()["flags_count"],
            self._integration.runtime.get_current_version(),
        )

        return self._integration

    async def shutdown(self) -> None:
        """
        Gracefully shutdown the platform.

        Shutdown sequence:
            1. Stop scheduler
            2. Complete active experiments
            3. Persist snapshot
            4. Flush audit events
            5. Shutdown runtime
        """
        if not self._started:
            return

        logger.info("Shutting down Feature Flag Platform...")

        await self._integration.shutdown()

        self._started = False
        logger.info("Feature Flag Platform stopped")

    async def reload(
        self,
        flags: Dict[str, Dict[str, Any]],
        operator: str = "system",
        reason: str = "reload",
    ) -> Dict[str, Any]:
        """
        Hot reload feature flags.

        Args:
            flags: New flag data.
            operator: Who triggered the reload.
            reason: Reason for reload.

        Returns:
            Reload result.
        """
        return await self._integration.reload(flags, operator, reason)

    def is_enabled(
        self,
        key: str,
        default: bool = False,
    ) -> bool:
        """
        Check if a feature flag is enabled.

        Args:
            key: Feature flag key.
            default: Default value.

        Returns:
            True if enabled.
        """
        return self._integration.is_enabled(key, default=default)

    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive platform statistics."""
        return {
            "started": self._started,
            "config": {
                "enabled": self._config.enabled,
                "cache_enabled": self._config.cache_enabled,
            },
            "integration": self._integration.get_stats(),
        }
