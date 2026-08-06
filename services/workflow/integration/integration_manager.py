"""Workflow Integration Manager — unified entry point for all platform integrations.

The :class:`WorkflowIntegrationManager` wires together every platform adapter
(service mesh, event bus, scheduler, business services, AI runtime, etc.) and
provides a single lifecycle for initialising, synchronising, and shutting down
the integrated workflow platform.

Architecture::

    WorkflowIntegrationManager
              │
    ┌─────────┼─────────┐
    Infrastructure   Business Domain   AI Runtime
    └─────────┼─────────┘
         PlatformRuntime
"""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from .platform_runtime import PlatformRuntime, PlatformRuntimeState
from .service_mesh_adapter import ServiceMeshAdapter
from .eventbus_adapter import EventBusAdapter
from .scheduler_adapter import SchedulerAdapter
from .configuration_adapter import ConfigurationAdapter
from .feature_flag_adapter import FeatureFlagAdapter
from .discovery_adapter import DiscoveryAdapter
from .secrets_adapter import SecretsAdapter
from .strategy_runtime_adapter import StrategyRuntimeAdapter
from .ai_runtime_adapter import AIRuntimeAdapter
from .order_adapter import OrderAdapter
from .risk_adapter import RiskAdapter
from .execution_adapter import ExecutionAdapter
from .settlement_adapter import SettlementAdapter
from .ledger_adapter import LedgerAdapter
from .notification_adapter import NotificationAdapter

logger = logging.getLogger(__name__)


class IntegrationState(str, Enum):
    """Lifecycle states of the integration manager."""

    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    ACTIVE = "active"
    DEGRADED = "degraded"
    STOPPING = "stopping"
    STOPPED = "stopped"


class WorkflowIntegrationManager:
    """Unified manager for all workflow platform integrations.

    Usage::

        mgr = WorkflowIntegrationManager()
        await mgr.initialize()
        await mgr.synchronize()
        await mgr.shutdown()
    """

    def __init__(self, *, name: str = "default") -> None:
        self._name = name
        self._state = IntegrationState.UNINITIALIZED
        self._lock = threading.RLock()
        self._started_at: Optional[datetime] = None

        # Runtime
        self._runtime: Optional[PlatformRuntime] = None

        # Infrastructure adapters
        self._service_mesh: Optional[ServiceMeshAdapter] = None
        self._eventbus: Optional[EventBusAdapter] = None
        self._scheduler: Optional[SchedulerAdapter] = None
        self._configuration: Optional[ConfigurationAdapter] = None
        self._feature_flag: Optional[FeatureFlagAdapter] = None
        self._discovery: Optional[DiscoveryAdapter] = None
        self._secrets: Optional[SecretsAdapter] = None

        # Business domain adapters
        self._order: Optional[OrderAdapter] = None
        self._risk: Optional[RiskAdapter] = None
        self._execution: Optional[ExecutionAdapter] = None
        self._settlement: Optional[SettlementAdapter] = None
        self._ledger: Optional[LedgerAdapter] = None
        self._notification: Optional[NotificationAdapter] = None

        # AI & Strategy
        self._strategy_runtime: Optional[StrategyRuntimeAdapter] = None
        self._ai_runtime: Optional[AIRuntimeAdapter] = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return self._name

    @property
    def state(self) -> IntegrationState:
        with self._lock:
            return self._state

    @property
    def is_active(self) -> bool:
        return self._state == IntegrationState.ACTIVE

    @property
    def service_mesh(self) -> Optional[ServiceMeshAdapter]:
        return self._service_mesh

    @property
    def eventbus(self) -> Optional[EventBusAdapter]:
        return self._eventbus

    @property
    def scheduler(self) -> Optional[SchedulerAdapter]:
        return self._scheduler

    @property
    def order(self) -> Optional[OrderAdapter]:
        return self._order

    @property
    def risk(self) -> Optional[RiskAdapter]:
        return self._risk

    @property
    def execution(self) -> Optional[ExecutionAdapter]:
        return self._execution

    @property
    def strategy_runtime(self) -> Optional[StrategyRuntimeAdapter]:
        return self._strategy_runtime

    @property
    def ai_runtime(self) -> Optional[AIRuntimeAdapter]:
        return self._ai_runtime

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(
        self,
        *,
        service_mesh_config: Optional[Dict[str, Any]] = None,
        eventbus_config: Optional[Dict[str, Any]] = None,
        scheduler_config: Optional[Dict[str, Any]] = None,
        config_config: Optional[Dict[str, Any]] = None,
        feature_flag_config: Optional[Dict[str, Any]] = None,
        discovery_config: Optional[Dict[str, Any]] = None,
        secrets_config: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialise all platform integrations."""
        with self._lock:
            if self._state == IntegrationState.ACTIVE:
                return
            self._state = IntegrationState.INITIALIZING
            self._started_at = datetime.utcnow()

        logger.info("IntegrationManager(%s): initialising …", self._name)

        # Platform runtime
        self._runtime = PlatformRuntime()
        await self._runtime.start()

        # Infrastructure adapters
        self._service_mesh = ServiceMeshAdapter(config=service_mesh_config or {})
        self._eventbus = EventBusAdapter(config=eventbus_config or {})
        self._scheduler = SchedulerAdapter(config=scheduler_config or {})
        self._configuration = ConfigurationAdapter(config=config_config or {})
        self._feature_flag = FeatureFlagAdapter(config=feature_flag_config or {})
        self._discovery = DiscoveryAdapter(config=discovery_config or {})
        self._secrets = SecretsAdapter(config=secrets_config or {})

        # Business domain adapters
        self._order = OrderAdapter()
        self._risk = RiskAdapter()
        self._execution = ExecutionAdapter()
        self._settlement = SettlementAdapter()
        self._ledger = LedgerAdapter()
        self._notification = NotificationAdapter()

        # AI & Strategy
        self._strategy_runtime = StrategyRuntimeAdapter()
        self._ai_runtime = AIRuntimeAdapter()

        # Start infrastructure adapters
        infra_adapters = [
            self._service_mesh, self._eventbus, self._scheduler,
            self._configuration, self._feature_flag, self._discovery, self._secrets,
        ]
        for adapter in infra_adapters:
            if adapter:
                await adapter.start()

        # Start business adapters
        biz_adapters = [
            self._order, self._risk, self._execution,
            self._settlement, self._ledger, self._notification,
        ]
        for adapter in biz_adapters:
            if adapter:
                await adapter.start()

        # Start AI & strategy
        if self._strategy_runtime:
            await self._strategy_runtime.start()
        if self._ai_runtime:
            await self._ai_runtime.start()

        with self._lock:
            self._state = IntegrationState.ACTIVE

        logger.info("IntegrationManager(%s): active", self._name)

    async def synchronize(self) -> Dict[str, Any]:
        """Synchronize all integration state."""
        result: Dict[str, Any] = {"timestamp": datetime.utcnow().isoformat()}

        if self._configuration:
            result["configuration"] = await self._configuration.sync()
        if self._feature_flag:
            result["feature_flags"] = await self._feature_flag.sync()
        if self._discovery:
            result["discovery"] = await self._discovery.sync()
        if self._service_mesh:
            result["service_mesh"] = await self._service_mesh.sync()

        return result

    async def shutdown(self) -> None:
        """Gracefully shut down all integrations."""
        with self._lock:
            if self._state == IntegrationState.STOPPED:
                return
            self._state = IntegrationState.STOPPING

        logger.info("IntegrationManager(%s): shutting down …", self._name)

        all_adapters = [
            self._ai_runtime, self._strategy_runtime,
            self._notification, self._ledger, self._settlement,
            self._execution, self._risk, self._order,
            self._secrets, self._discovery, self._feature_flag,
            self._configuration, self._scheduler, self._eventbus,
            self._service_mesh,
        ]

        for adapter in all_adapters:
            if adapter:
                try:
                    await adapter.stop()
                except Exception:
                    logger.exception("IntegrationManager: error stopping adapter %s", type(adapter).__name__)

        if self._runtime:
            await self._runtime.stop()

        with self._lock:
            self._state = IntegrationState.STOPPED

        logger.info("IntegrationManager(%s): stopped", self._name)

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def list_adapters(self) -> Dict[str, bool]:
        """Return the enabled/disabled status of each adapter."""
        return {
            "service_mesh": self._service_mesh is not None,
            "eventbus": self._eventbus is not None,
            "scheduler": self._scheduler is not None,
            "configuration": self._configuration is not None,
            "feature_flag": self._feature_flag is not None,
            "discovery": self._discovery is not None,
            "secrets": self._secrets is not None,
            "order": self._order is not None,
            "risk": self._risk is not None,
            "execution": self._execution is not None,
            "settlement": self._settlement is not None,
            "ledger": self._ledger is not None,
            "notification": self._notification is not None,
            "strategy_runtime": self._strategy_runtime is not None,
            "ai_runtime": self._ai_runtime is not None,
        }

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        report: Dict[str, Any] = {
            "name": self._name,
            "state": self._state.value,
            "started_at": self._started_at.isoformat() if self._started_at else None,
        }
        if self._runtime:
            report["runtime"] = self._runtime.health_report()
        if self._service_mesh:
            report["service_mesh"] = self._service_mesh.health_report()
        if self._eventbus:
            report["eventbus"] = self._eventbus.health_report()
        return report
