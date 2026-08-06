"""Scheduler Integration Manager — unified platform integration entry point.

The :class:`SchedulerIntegrationManager` coordinates all platform adapters:
* Initialization — boot all adapters in dependency order
* Synchronization — keep scheduler state aligned with platform
* Shutdown — graceful teardown of all integrations

Architecture::

    SchedulerIntegrationManager
              │
    ┌─────────┼──────────┐
    Infrastructure  Business   Observability
    └─────────┼──────────┘
         PlatformRuntime → Workflow Engine
"""

from __future__ import annotations

import asyncio
import enum
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class IntegrationState(enum.Enum):
    """Integration manager lifecycle states."""

    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    INITIALIZED = "initialized"
    SYNCHRONIZING = "synchronizing"
    SYNCHRONIZED = "synchronized"
    DEGRADED = "degraded"
    SHUTTING_DOWN = "shutting_down"
    SHUTDOWN = "shutdown"
    ERROR = "error"


class SchedulerIntegrationManager:
    """Unified platform integration manager.

    Responsibilities:
    * Boot all adapters in correct dependency order
    * Health-check each adapter periodically
    * Synchronize scheduler state with platform services
    * Graceful shutdown of all integrations

    Usage::

        manager = SchedulerIntegrationManager(scheduler_engine=engine)
        await manager.initialize()
        await manager.synchronize()
        # ... runtime ...
        await manager.shutdown()
    """

    def __init__(self, scheduler_engine: Any = None) -> None:
        self._engine = scheduler_engine
        self._state = IntegrationState.UNINITIALIZED
        self._lock = threading.Lock()
        self._adapters: Dict[str, Any] = {}
        self._started_at: Optional[datetime] = None
        self._last_sync_at: Optional[datetime] = None
        self._sync_count: int = 0
        self._error_count: int = 0
        self._last_error: Optional[str] = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def state(self) -> IntegrationState:
        return self._state

    @property
    def adapters(self) -> Dict[str, Any]:
        return dict(self._adapters)

    @property
    def started_at(self) -> Optional[datetime]:
        return self._started_at

    @property
    def last_sync_at(self) -> Optional[datetime]:
        return self._last_sync_at

    @property
    def sync_count(self) -> int:
        return self._sync_count

    @property
    def error_count(self) -> int:
        return self._error_count

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Initialize all platform adapters in dependency order."""
        self._set_state(IntegrationState.INITIALIZING)
        self._started_at = datetime.now(timezone.utc)
        logger.info("SchedulerIntegrationManager: initializing platform adapters")

        # Phase 1 — Infrastructure (no dependencies)
        await self._init_infrastructure()

        # Phase 2 — Observability (depends on infrastructure)
        await self._init_observability()

        # Phase 3 — Business Domains (depend on infrastructure)
        await self._init_business_domains()

        # Phase 4 — External Interfaces (depend on all above)
        await self._init_external_interfaces()

        self._set_state(IntegrationState.INITIALIZED)
        logger.info("SchedulerIntegrationManager: initialized (%d adapters)", len(self._adapters))

    async def synchronize(self) -> Dict[str, Any]:
        """Synchronize scheduler state across all platform adapters."""
        self._set_state(IntegrationState.SYNCHRONIZING)
        results: Dict[str, Any] = {}

        try:
            for name, adapter in self._adapters.items():
                if hasattr(adapter, "synchronize"):
                    results[name] = await adapter.synchronize()
            self._last_sync_at = datetime.now(timezone.utc)
            self._sync_count += 1
            self._set_state(IntegrationState.SYNCHRONIZED)
        except Exception as exc:
            self._error_count += 1
            self._last_error = str(exc)
            self._set_state(IntegrationState.DEGRADED)
            logger.error("SchedulerIntegrationManager: sync failed: %s", exc)

        return results

    async def shutdown(self) -> None:
        """Gracefully shutdown all adapters in reverse dependency order."""
        self._set_state(IntegrationState.SHUTTING_DOWN)
        logger.info("SchedulerIntegrationManager: shutting down")

        # Reverse order: external interfaces → business → observability → infra
        phases = [
            "_shutdown_external_interfaces",
            "_shutdown_business_domains",
            "_shutdown_observability",
            "_shutdown_infrastructure",
        ]
        for phase_method in phases:
            try:
                await getattr(self, phase_method)()
            except Exception as exc:
                logger.warning("SchedulerIntegrationManager: %s error: %s", phase_method, exc)

        self._set_state(IntegrationState.SHUTDOWN)
        logger.info("SchedulerIntegrationManager: shutdown complete")

    # ------------------------------------------------------------------
    # Adapter Registration
    # ------------------------------------------------------------------

    def register_adapter(self, name: str, adapter: Any) -> None:
        """Register an adapter with the integration manager."""
        self._adapters[name] = adapter
        logger.debug("SchedulerIntegrationManager: registered adapter '%s'", name)

    def get_adapter(self, name: str) -> Optional[Any]:
        """Retrieve a registered adapter by name."""
        return self._adapters.get(name)

    # ------------------------------------------------------------------
    # Private — Initialization Phases
    # ------------------------------------------------------------------

    async def _init_infrastructure(self) -> None:
        """Phase 1: Infrastructure adapters."""
        # Configuration, Discovery, Secrets, Service Mesh, Feature Flags
        pass

    async def _init_observability(self) -> None:
        """Phase 2: Observability adapters."""
        # Telemetry, Tracing, Metrics
        pass

    async def _init_business_domains(self) -> None:
        """Phase 3: Business domain adapters."""
        # Workflow, EventBus, Strategy, AI, Research, Market, OMS, etc.
        pass

    async def _init_external_interfaces(self) -> None:
        """Phase 4: External interfaces (Dashboard, SDK, CLI)."""
        pass

    async def _shutdown_external_interfaces(self) -> None:
        pass

    async def _shutdown_business_domains(self) -> None:
        pass

    async def _shutdown_observability(self) -> None:
        pass

    async def _shutdown_infrastructure(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Private — State
    # ------------------------------------------------------------------

    def _set_state(self, state: IntegrationState) -> None:
        with self._lock:
            self._state = state
