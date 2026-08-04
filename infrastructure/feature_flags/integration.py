"""
Feature flag platform integration layer.

Provides high-level integration between
all feature flag platform components,
simplifying common operations and
ensuring consistent behavior.

Integration covers:
    - Service ↔ Runtime ↔ Snapshot
    - Canary ↔ Experiment ↔ Evaluation
    - Protection ↔ Recovery ↔ Telemetry
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from .container import ServiceContainer
from .events import EventBus, FeatureEvent, FeatureEventType
from .hotreload import HotReloadManager
from .lifecycle import PlatformLifecycle
from .monitoring import FeatureFlagRuntimeMetrics
from .protection import PlatformProtection
from .publisher import FeatureEventPublisher
from .recovery import RecoveryManager
from .runtime import RuntimeFeatureService
from .scheduler import FeatureFlagScheduler
from .snapshot import SnapshotManager
from .subscriber import FeatureEventSubscriber
from .synchronization import SynchronizationManager
from .telemetry import FeatureFlagTelemetry

logger = logging.getLogger(__name__)


class PlatformIntegration:
    """
    High-level integration for the feature flag platform.

    Provides a unified entry point that wires together
    all platform components and provides simplified
    access to common operations.

    Architecture:
        ┌──────────────────────────────────────────┐
        │         PlatformIntegration              │
        │                                          │
        │  ┌────────────┐  ┌──────────────────┐   │
        │  │  Container  │  │  Lifecycle       │   │
        │  └─────┬──────┘  └────────┬─────────┘   │
        │        │                    │             │
        │  ┌─────▼──────┐  ┌────────▼─────────┐   │
        │  │  Runtime   │  │  Hot Reload      │   │
        │  └─────┬──────┘  └────────┬─────────┘   │
        │        │                    │             │
        │  ┌─────▼──────┐  ┌────────▼─────────┐   │
        │  │  Protect   │  │  Recovery        │   │
        │  └────────────┘  └──────────────────┘   │
        │                                          │
        │  ┌────────────┐  ┌──────────────────┐   │
        │  │  Scheduler │  │  Sync            │   │
        │  └─────┬──────┘  └────────┬─────────┘   │
        │        │                    │             │
        │  ┌─────▼──────┐  ┌────────▼─────────┐   │
        │  │  Telemetry │  │  EventBus        │   │
        │  └────────────┘  └──────────────────┘   │
        └──────────────────────────────────────────┘

    Usage:
        integration = PlatformIntegration()
        await integration.start()

        # Evaluate flags
        result = await integration.evaluate("my.flag")

        # Hot reload
        await integration.reload(flags)

        await integration.shutdown()
    """

    def __init__(self) -> None:
        """Initialize platform integration."""
        # Core infrastructure
        self._container = ServiceContainer()
        self._event_bus = EventBus()
        self._snapshot_mgr = SnapshotManager()

        # Runtime
        self._runtime = RuntimeFeatureService()
        self._hot_reload = HotReloadManager(
            runtime=self._runtime,
            publisher=FeatureEventPublisher(self._event_bus),
        )

        # Protection and recovery
        self._protection = PlatformProtection()
        self._recovery = RecoveryManager(
            hot_reload=self._hot_reload,
            runtime=self._runtime,
        )

        # Scheduling and sync
        self._scheduler = FeatureFlagScheduler()
        self._sync = SynchronizationManager(
            event_bus=self._event_bus,
            runtime=self._runtime,
        )

        # Telemetry
        self._telemetry = FeatureFlagTelemetry(
            event_bus=self._event_bus,
            metrics=self._hot_reload.publisher.bus and None,
        )
        self._metrics = self._telemetry._metrics

        # Subscriber
        self._subscriber = FeatureEventSubscriber(
            event_bus=self._event_bus,
        )

        # Lifecycle
        self._lifecycle = PlatformLifecycle()

        # Register services
        self._register_services()

    def _register_services(self) -> None:
        """Register all services in the container."""
        self._container.register_singleton(ServiceContainer, self._container)
        self._container.register_singleton(EventBus, self._event_bus)
        self._container.register_singleton(
            SnapshotManager, self._snapshot_mgr,
        )
        self._container.register_singleton(
            RuntimeFeatureService, self._runtime,
        )
        self._container.register_singleton(
            HotReloadManager, self._hot_reload,
        )
        self._container.register_singleton(
            PlatformProtection, self._protection,
        )
        self._container.register_singleton(
            RecoveryManager, self._recovery,
        )
        self._container.register_singleton(
            FeatureFlagScheduler, self._scheduler,
        )
        self._container.register_singleton(
            SynchronizationManager, self._sync,
        )
        self._container.register_singleton(
            FeatureFlagTelemetry, self._telemetry,
        )
        self._container.register_singleton(
            FeatureEventSubscriber, self._subscriber,
        )
        self._container.register_singleton(
            PlatformLifecycle, self._lifecycle,
        )

    @property
    def container(self) -> ServiceContainer:
        """Get the DI container."""
        return self._container

    @property
    def runtime(self) -> RuntimeFeatureService:
        """Get the runtime service."""
        return self._runtime

    @property
    def hot_reload(self) -> HotReloadManager:
        """Get the hot reload manager."""
        return self._hot_reload

    @property
    def protection(self) -> PlatformProtection:
        """Get the platform protection."""
        return self._protection

    @property
    def recovery(self) -> RecoveryManager:
        """Get the recovery manager."""
        return self._recovery

    @property
    def scheduler(self) -> FeatureFlagScheduler:
        """Get the scheduler."""
        return self._scheduler

    @property
    def sync(self) -> SynchronizationManager:
        """Get the sync manager."""
        return self._sync

    @property
    def telemetry(self) -> FeatureFlagTelemetry:
        """Get the telemetry handler."""
        return self._telemetry

    @property
    def event_bus(self) -> EventBus:
        """Get the event bus."""
        return self._event_bus

    async def start(self) -> None:
        """
        Start all platform components.

        Executes lifecycle hooks in order:
            1. Start telemetry
            2. Start subscriber
            3. Init runtime
            4. Start scheduler
            5. Start sync
        """
        # Register startup hooks
        self._lifecycle.add_startup_hook(
            "telemetry",
            self._telemetry.start,
            order=0,
        )
        self._lifecycle.add_startup_hook(
            "subscriber",
            self._subscriber.subscribe_all,
            order=1,
        )
        self._lifecycle.add_startup_hook(
            "runtime",
            lambda: self._runtime.start(),
            order=2,
        )
        self._lifecycle.add_startup_hook(
            "scheduler",
            self._scheduler.start,
            order=3,
        )
        self._lifecycle.add_startup_hook(
            "sync",
            self._sync.start,
            order=4,
        )

        # Register shutdown hooks (reverse order)
        self._lifecycle.add_shutdown_hook(
            "scheduler",
            self._scheduler.stop,
            order=0,
        )
        self._lifecycle.add_shutdown_hook(
            "telemetry",
            self._telemetry.shutdown,
            order=1,
        )
        self._lifecycle.add_shutdown_hook(
            "event_bus",
            self._event_bus.shutdown,
            order=2,
        )

        await self._lifecycle.start()

    async def shutdown(self) -> None:
        """
        Shutdown all platform components.

        Graceful shutdown:
            1. Stop scheduler
            2. Persist snapshot
            3. Flush telemetry
            4. Shutdown runtime
        """
        # Persist current snapshot
        snapshot = self._runtime.get_snapshot()
        if snapshot:
            await self._hot_reload.publisher.publish_snapshot_activated(
                data={"version": snapshot.version},
            )

        await self._lifecycle.shutdown()

    async def evaluate(
        self,
        key: str,
        context: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate a feature flag.

        Protected by rate limiting and circuit breaker.

        Args:
            key: Feature flag key.
            context: Evaluation context.

        Returns:
            Evaluation result.
        """
        if not self._protection.can_evaluate():
            return {
                "key": key,
                "value": False,
                "reason": "protection_blocked",
            }

        start = asyncio.get_event_loop().time()

        try:
            result = await self._runtime.evaluate(key, context)
            latency_ms = (asyncio.get_event_loop().time() - start) * 1000
            self._metrics.record_evaluation(latency_ms=latency_ms)
            self._protection.record_result(True)
            return result
        except Exception as e:
            self._protection.record_result(False)
            self._recovery.recover(str(e))
            return {
                "key": key,
                "value": False,
                "reason": f"error: {e}",
            }

    async def reload(
        self,
        flags: Dict[str, Dict[str, Any]],
        operator: str = "system",
        reason: str = "manual_reload",
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
        return await self._hot_reload.reload(flags, operator, reason)

    def is_enabled(
        self,
        key: str,
        context: Optional[Any] = None,
        default: bool = False,
    ) -> bool:
        """
        Check if a feature flag is enabled (lock-free).

        Args:
            key: Feature flag key.
            context: Evaluation context.
            default: Default value.

        Returns:
            True if enabled.
        """
        return self._runtime.is_enabled(key, context, default)

    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive platform statistics."""
        return {
            "lifecycle": self._lifecycle.get_stats(),
            "runtime": self._runtime.get_stats(),
            "scheduler": self._scheduler.get_stats(),
            "protection": self._protection.get_stats(),
            "recovery": self._recovery.get_stats(),
            "sync": self._sync.get_stats(),
            "telemetry": self._telemetry.get_stats(),
            "container": self._container.get_stats(),
        }
