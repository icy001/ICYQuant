"""Integration Manager — unified research platform orchestration.

Commit 11 Part 1.5: Central coordinator for all integration adapters.

Architecture::

    ResearchIntegrationManager
        ├── PlatformRuntime       (lifecycle)
        ├── WorkflowAdapter       → Workflow Engine
        ├── SchedulerAdapter      → Distributed Scheduler
        ├── EventBusAdapter       → EventBus
        ├── StrategyRuntimeAdapter → Strategy Runtime
        ├── ExecutionAdapter      → Execution Engine
        ├── MarketDataAdapter     → Market Data
        ├── FeatureStoreAdapter   → Feature Store
        ├── ModelRegistry         → Model Management
        ├── AIRuntimeAdapter      → AI Runtime
        ├── ReportCenter          → Report Generation
        ├── DashboardAPI          → Dashboard Endpoints
        ├── ResearchSDK           → Python SDK
        └── ResearchCLI           → CLI Tool

The :class:`ResearchIntegrationManager` is the single entry point for
initializing, synchronizing, and shutting down the unified research platform.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class PlatformState(str, Enum):
    """Unified research platform lifecycle states."""

    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    INITIALIZED = "initialized"
    SYNCHRONIZING = "synchronizing"
    READY = "ready"
    RUNNING = "running"
    DEGRADED = "degraded"
    SHUTTING_DOWN = "shutting_down"
    TERMINATED = "terminated"
    ERROR = "error"


class ResearchIntegrationManager:
    """Unified research platform orchestration manager.

    Coordinates all integration adapters and provides a single entry point
    for initializing, running, and shutting down the unified research platform.

    Usage::

        manager = ResearchIntegrationManager(config=config)
        await manager.initialize()
        await manager.synchronize()
        # ... run research workflows ...
        await manager.shutdown()
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        *,
        platform_id: Optional[str] = None,
    ) -> None:
        self._id: str = platform_id or f"rip-{uuid4().hex[:12]}"
        self._config: Dict[str, Any] = config or {}
        self._state: PlatformState = PlatformState.UNINITIALIZED
        self._created_at: datetime = datetime.now(timezone.utc)
        self._initialized_at: Optional[datetime] = None

        # Adapter references — populated during initialize()
        self._platform_runtime: Any = None
        self._workflow_adapter: Any = None
        self._scheduler_adapter: Any = None
        self._eventbus_adapter: Any = None
        self._strategy_runtime_adapter: Any = None
        self._execution_adapter: Any = None
        self._market_data_adapter: Any = None
        self._feature_store_adapter: Any = None
        self._model_registry: Any = None
        self._ai_runtime_adapter: Any = None
        self._report_center: Any = None
        self._dashboard_api: Any = None
        self._sdk: Any = None
        self._cli: Any = None

        # Initialization order
        self._init_order: List[str] = [
            "platform_runtime",
            "eventbus",
            "market_data",
            "feature_store",
            "model_registry",
            "workflow",
            "scheduler",
            "strategy_runtime",
            "execution",
            "ai_runtime",
            "report_center",
            "dashboard",
            "sdk",
            "cli",
        ]
        self._init_status: Dict[str, bool] = {}

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def id(self) -> str:
        return self._id

    @property
    def state(self) -> PlatformState:
        return self._state

    @property
    def config(self) -> Dict[str, Any]:
        return dict(self._config)

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def initialized_at(self) -> Optional[datetime]:
        return self._initialized_at

    @property
    def is_ready(self) -> bool:
        return self._state == PlatformState.READY

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Initialize all integration adapters in dependency order."""
        if self._state not in (PlatformState.UNINITIALIZED, PlatformState.TERMINATED):
            logger.warning("IntegrationManager already initialized (state=%s)", self._state.value)
            return

        self._state = PlatformState.INITIALIZING
        logger.info("Initializing Research Integration Manager [%s]...", self._id)

        from .platform_runtime import PlatformRuntime

        self._platform_runtime = PlatformRuntime(config=self._config)
        await self._platform_runtime.initialize()
        self._init_status["platform_runtime"] = True

        # EventBus — needed early for event-driven communication
        try:
            from .eventbus_adapter import EventBusAdapter

            self._eventbus_adapter = EventBusAdapter(config=self._config)
            await self._eventbus_adapter.initialize()
            self._init_status["eventbus"] = True
        except Exception as exc:
            logger.warning("EventBus adapter unavailable: %s", exc)
            self._init_status["eventbus"] = False

        # Market Data
        try:
            from .market_data_adapter import MarketDataAdapter

            self._market_data_adapter = MarketDataAdapter(config=self._config)
            await self._market_data_adapter.initialize()
            self._init_status["market_data"] = True
        except Exception as exc:
            logger.warning("MarketData adapter unavailable: %s", exc)
            self._init_status["market_data"] = False

        # Feature Store
        try:
            from .feature_store_adapter import FeatureStoreAdapter

            self._feature_store_adapter = FeatureStoreAdapter(config=self._config)
            await self._feature_store_adapter.initialize()
            self._init_status["feature_store"] = True
        except Exception as exc:
            logger.warning("FeatureStore adapter unavailable: %s", exc)
            self._init_status["feature_store"] = False

        # Model Registry
        try:
            from .model_registry import ModelRegistry

            self._model_registry = ModelRegistry(config=self._config)
            await self._model_registry.initialize()
            self._init_status["model_registry"] = True
        except Exception as exc:
            logger.warning("ModelRegistry unavailable: %s", exc)
            self._init_status["model_registry"] = False

        # Workflow Adapter
        try:
            from .workflow_adapter import WorkflowAdapter

            self._workflow_adapter = WorkflowAdapter(config=self._config)
            await self._workflow_adapter.initialize()
            self._init_status["workflow"] = True
        except Exception as exc:
            logger.warning("Workflow adapter unavailable: %s", exc)
            self._init_status["workflow"] = False

        # Scheduler Adapter
        try:
            from .scheduler_adapter import SchedulerAdapter

            self._scheduler_adapter = SchedulerAdapter(config=self._config)
            await self._scheduler_adapter.initialize()
            self._init_status["scheduler"] = True
        except Exception as exc:
            logger.warning("Scheduler adapter unavailable: %s", exc)
            self._init_status["scheduler"] = False

        # Strategy Runtime
        try:
            from .strategy_runtime_adapter import StrategyRuntimeAdapter

            self._strategy_runtime_adapter = StrategyRuntimeAdapter(config=self._config)
            await self._strategy_runtime_adapter.initialize()
            self._init_status["strategy_runtime"] = True
        except Exception as exc:
            logger.warning("StrategyRuntime adapter unavailable: %s", exc)
            self._init_status["strategy_runtime"] = False

        # Execution Adapter
        try:
            from .execution_adapter import ExecutionAdapter

            self._execution_adapter = ExecutionAdapter(config=self._config)
            await self._execution_adapter.initialize()
            self._init_status["execution"] = True
        except Exception as exc:
            logger.warning("Execution adapter unavailable: %s", exc)
            self._init_status["execution"] = False

        # AI Runtime
        try:
            from .ai_runtime_adapter import AIRuntimeAdapter

            self._ai_runtime_adapter = AIRuntimeAdapter(config=self._config)
            await self._ai_runtime_adapter.initialize()
            self._init_status["ai_runtime"] = True
        except Exception as exc:
            logger.warning("AI Runtime adapter unavailable: %s", exc)
            self._init_status["ai_runtime"] = False

        # Report Center
        try:
            from .report_center import ReportCenter

            self._report_center = ReportCenter(config=self._config)
            await self._report_center.initialize()
            self._init_status["report_center"] = True
        except Exception as exc:
            logger.warning("ReportCenter unavailable: %s", exc)
            self._init_status["report_center"] = False

        # Dashboard API
        try:
            from .dashboard_api import DashboardAPI

            self._dashboard_api = DashboardAPI(config=self._config)
            await self._dashboard_api.initialize()
            self._init_status["dashboard"] = True
        except Exception as exc:
            logger.warning("DashboardAPI unavailable: %s", exc)
            self._init_status["dashboard"] = False

        # SDK
        try:
            from .sdk import ResearchSDK

            self._sdk = ResearchSDK(config=self._config)
            self._init_status["sdk"] = True
        except Exception as exc:
            logger.warning("SDK unavailable: %s", exc)
            self._init_status["sdk"] = False

        # CLI
        try:
            from .cli import ResearchCLI

            self._cli = ResearchCLI(config=self._config)
            self._init_status["cli"] = True
        except Exception as exc:
            logger.warning("CLI unavailable: %s", exc)
            self._init_status["cli"] = False

        self._initialized_at = datetime.now(timezone.utc)
        self._state = PlatformState.INITIALIZED
        logger.info(
            "Research Integration Manager initialized [%s] — %d/%d adapters ready",
            self._id,
            sum(self._init_status.values()),
            len(self._init_status),
        )

    async def synchronize(self) -> Dict[str, Any]:
        """Synchronize all adapters and validate platform readiness.

        Returns:
            Dict with sync status for each adapter.
        """
        self._state = PlatformState.SYNCHRONIZING
        sync_results: Dict[str, Any] = {"platform_id": self._id, "timestamp": datetime.now(timezone.utc).isoformat()}

        adapters = [
            ("workflow", self._workflow_adapter),
            ("scheduler", self._scheduler_adapter),
            ("eventbus", self._eventbus_adapter),
            ("strategy_runtime", self._strategy_runtime_adapter),
            ("execution", self._execution_adapter),
            ("market_data", self._market_data_adapter),
            ("feature_store", self._feature_store_adapter),
            ("model_registry", self._model_registry),
            ("ai_runtime", self._ai_runtime_adapter),
            ("report_center", self._report_center),
        ]

        for name, adapter in adapters:
            if adapter is not None and hasattr(adapter, "synchronize"):
                try:
                    result = await adapter.synchronize()
                    sync_results[name] = {"status": "ok", "detail": result}
                except Exception as exc:
                    sync_results[name] = {"status": "error", "detail": str(exc)}
            else:
                sync_results[name] = {"status": "skipped"}

        # Validate overall health
        ok_count = sum(1 for v in sync_results.values() if isinstance(v, dict) and v.get("status") in ("ok", "skipped"))
        if ok_count == len(adapters):
            self._state = PlatformState.READY
        else:
            self._state = PlatformState.DEGRADED

        logger.info("Platform sync complete [%s]: %d/%d healthy", self._id, ok_count, len(adapters))
        return sync_results

    async def shutdown(self) -> None:
        """Gracefully shutdown all integration adapters."""
        self._state = PlatformState.SHUTTING_DOWN
        logger.info("Shutting down Research Integration Manager [%s]...", self._id)

        # Shutdown in reverse initialization order
        adapters_reversed = [
            ("cli", self._cli),
            ("sdk", self._sdk),
            ("dashboard", self._dashboard_api),
            ("report_center", self._report_center),
            ("ai_runtime", self._ai_runtime_adapter),
            ("execution", self._execution_adapter),
            ("strategy_runtime", self._strategy_runtime_adapter),
            ("scheduler", self._scheduler_adapter),
            ("workflow", self._workflow_adapter),
            ("model_registry", self._model_registry),
            ("feature_store", self._feature_store_adapter),
            ("market_data", self._market_data_adapter),
            ("eventbus", self._eventbus_adapter),
            ("platform_runtime", self._platform_runtime),
        ]

        for name, adapter in adapters_reversed:
            if adapter is not None and hasattr(adapter, "shutdown"):
                try:
                    await adapter.shutdown()
                    logger.debug("Shutdown complete: %s", name)
                except Exception as exc:
                    logger.warning("Shutdown error for %s: %s", name, exc)

        self._state = PlatformState.TERMINATED
        logger.info("Research Integration Manager terminated [%s]", self._id)

    # ------------------------------------------------------------------
    # Adapter Access
    # ------------------------------------------------------------------

    @property
    def workflow(self) -> Any:
        if self._workflow_adapter is None:
            raise RuntimeError("Workflow adapter not initialized")
        return self._workflow_adapter

    @property
    def scheduler(self) -> Any:
        if self._scheduler_adapter is None:
            raise RuntimeError("Scheduler adapter not initialized")
        return self._scheduler_adapter

    @property
    def eventbus(self) -> Any:
        if self._eventbus_adapter is None:
            raise RuntimeError("EventBus adapter not initialized")
        return self._eventbus_adapter

    @property
    def model_registry(self) -> Any:
        if self._model_registry is None:
            raise RuntimeError("ModelRegistry not initialized")
        return self._model_registry

    @property
    def ai_runtime(self) -> Any:
        if self._ai_runtime_adapter is None:
            raise RuntimeError("AI Runtime adapter not initialized")
        return self._ai_runtime_adapter

    @property
    def report_center(self) -> Any:
        if self._report_center is None:
            raise RuntimeError("ReportCenter not initialized")
        return self._report_center

    @property
    def sdk(self) -> Any:
        if self._sdk is None:
            raise RuntimeError("SDK not initialized")
        return self._sdk

    @property
    def cli(self) -> Any:
        if self._cli is None:
            raise RuntimeError("CLI not initialized")
        return self._cli

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    async def status(self) -> Dict[str, Any]:
        """Return comprehensive platform status."""
        return {
            "platform_id": self._id,
            "state": self._state.value,
            "created_at": self._created_at.isoformat(),
            "initialized_at": self._initialized_at.isoformat() if self._initialized_at else None,
            "adapters": self._init_status,
            "healthy_adapters": sum(self._init_status.values()),
            "total_adapters": len(self._init_status),
        }

    async def health_check(self) -> Dict[str, Any]:
        """Perform a full health check across all adapters."""
        status = await self.status()
        health: Dict[str, Any] = {"platform_id": self._id, "overall": "UP"}

        if status["healthy_adapters"] == 0:
            health["overall"] = "DOWN"
        elif status["healthy_adapters"] < status["total_adapters"]:
            health["overall"] = "DEGRADED"

        health["details"] = status
        return health
