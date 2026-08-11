"""
ICYQuant Unified Data Platform — Core Engine.

Commit 16 Part 1.5 — The single entry point that integrates all four data
subsystems (Market Connectivity, Market Data Normalization, Data Lake,
Streaming) into a unified data access layer for the entire ICYQuant platform.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from .data_gateway import DataGateway
from .data_runtime import DataPlatformRuntime, DataPlatformRuntimeStatus
from .data_manager import DataPlatformManager
from .data_controller import DataPlatformController
from .data_orchestrator import DataOrchestrator
from .data_pipeline import UnifiedDataPipeline
from .connectivity_adapter import ConnectivityAdapter
from .normalization_adapter import NormalizationAdapter
from .data_lake_adapter import DataLakeAdapter
from .streaming_adapter import StreamingAdapter
from .market_data_service import MarketDataService
from .historical_data_service import HistoricalDataService
from .replay_service import ReplayService
from .data_catalog import DataCatalog
from .metadata_service import MetadataService
from .schema_service import SchemaService
from .data_governance import DataGovernance
from .lineage_service import LineageService
from .quality_service import QualityService
from .retention_service import RetentionService
from .data_access_control import DataAccessControl
from .permission_manager import PermissionManager
from .audit_service import AuditService
from .api_gateway import APIGateway
from .sdk import DataSDK
from .observability import PlatformObservability
from .control_plane import DataControlPlane
from .metrics import DataPlatformMetrics
from .telemetry import DataPlatformTelemetry
from .diagnostics import DataPlatformDiagnostics
from .health import DataPlatformHealthChecker, DataPlatformHealthStatus

logger = logging.getLogger(__name__)


class PlatformState(str, Enum):
    """Unified data platform lifecycle states."""
    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    INITIALIZED = "initialized"
    STARTING = "starting"
    RUNNING = "running"
    PAUSING = "pausing"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    DEGRADED = "degraded"
    ERROR = "error"


@dataclass
class DataPlatformConfig:
    """Configuration for the unified data platform."""
    name: str = "icyquant-data-platform"
    version: str = "1.0.0"
    enable_connectivity: bool = True
    enable_normalization: bool = True
    enable_data_lake: bool = True
    enable_streaming: bool = True
    enable_governance: bool = True
    enable_access_control: bool = True
    enable_audit: bool = True
    enable_api_gateway: bool = True
    enable_control_plane: bool = True
    max_concurrent_requests: int = 10_000
    request_timeout_seconds: float = 30.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PlatformInfo:
    """Runtime information about the data platform."""
    name: str = ""
    version: str = ""
    state: PlatformState = PlatformState.UNINITIALIZED
    uptime_seconds: float = 0.0
    total_requests: int = 0
    active_connections: int = 0
    datasets_registered: int = 0
    schemas_registered: int = 0
    quality_checks_passed: int = 0
    subscribers: list[str] = field(default_factory=list)


class DataPlatform:
    """Unified Data Platform — the single entry point for all data operations.

    Integrates:
      - Market Connectivity (exchange connections)
      - Market Data Normalization (canonical model)
      - Historical Data Lake (versioned storage)
      - Real-Time Streaming (pub/sub messaging)

    Provides unified APIs through:
      - Data Gateway (subscribe/query/replay/publish)
      - Data Orchestrator (permission → catalog → route → respond)
      - Data Governance (metadata, lineage, quality, lifecycle)
      - Access Control (RBAC + ABAC)
      - API Gateway (REST/gRPC/WebSocket/GraphQL)
      - Control Plane (health, diagnostics, metrics)
    """

    def __init__(self, config: Optional[DataPlatformConfig] = None) -> None:
        self._config = config or DataPlatformConfig()
        self._state = PlatformState.UNINITIALIZED
        self._started_at: Optional[datetime] = None
        self._initialized = False

        # Subsystems
        self._runtime: Optional[DataPlatformRuntime] = None
        self._manager: Optional[DataPlatformManager] = None
        self._controller: Optional[DataPlatformController] = None
        self._gateway: Optional[DataGateway] = None
        self._orchestrator: Optional[DataOrchestrator] = None
        self._pipeline: Optional[UnifiedDataPipeline] = None

        # Adapters
        self._connectivity_adapter: Optional[ConnectivityAdapter] = None
        self._normalization_adapter: Optional[NormalizationAdapter] = None
        self._data_lake_adapter: Optional[DataLakeAdapter] = None
        self._streaming_adapter: Optional[StreamingAdapter] = None

        # Services
        self._market_data_service: Optional[MarketDataService] = None
        self._historical_data_service: Optional[HistoricalDataService] = None
        self._replay_service: Optional[ReplayService] = None
        self._data_catalog: Optional[DataCatalog] = None
        self._metadata_service: Optional[MetadataService] = None
        self._schema_service: Optional[SchemaService] = None

        # Governance
        self._governance: Optional[DataGovernance] = None
        self._lineage_service: Optional[LineageService] = None
        self._quality_service: Optional[QualityService] = None
        self._retention_service: Optional[RetentionService] = None

        # Security
        self._access_control: Optional[DataAccessControl] = None
        self._permission_manager: Optional[PermissionManager] = None
        self._audit_service: Optional[AuditService] = None

        # API
        self._api_gateway: Optional[APIGateway] = None
        self._sdk: Optional[DataSDK] = None

        # Observability
        self._observability: Optional[PlatformObservability] = None
        self._control_plane: Optional[DataControlPlane] = None
        self._metrics: Optional[DataPlatformMetrics] = None
        self._telemetry: Optional[DataPlatformTelemetry] = None
        self._diagnostics: Optional[DataPlatformDiagnostics] = None
        self._health_checker: Optional[DataPlatformHealthChecker] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Initialize the data platform and all subsystems."""
        if self._initialized:
            return

        self._state = PlatformState.INITIALIZING
        logger.info("Initializing ICYQuant Unified Data Platform v%s", self._config.version)

        self._runtime = DataPlatformRuntime()
        self._manager = DataPlatformManager()
        self._controller = DataPlatformController()

        self._metrics = DataPlatformMetrics()
        self._telemetry = DataPlatformTelemetry()
        self._diagnostics = DataPlatformDiagnostics()
        self._health_checker = DataPlatformHealthChecker()

        if self._config.enable_connectivity:
            self._connectivity_adapter = ConnectivityAdapter()
            await self._connectivity_adapter.initialize()

        if self._config.enable_normalization:
            self._normalization_adapter = NormalizationAdapter()
            await self._normalization_adapter.initialize()

        if self._config.enable_data_lake:
            self._data_lake_adapter = DataLakeAdapter()
            await self._data_lake_adapter.initialize()

        if self._config.enable_streaming:
            self._streaming_adapter = StreamingAdapter()
            await self._streaming_adapter.initialize()

        self._market_data_service = MarketDataService(
            connectivity=self._connectivity_adapter,
            normalization=self._normalization_adapter,
        )
        self._historical_data_service = HistoricalDataService(
            data_lake=self._data_lake_adapter,
        )
        self._replay_service = ReplayService(
            data_lake=self._data_lake_adapter,
            streaming=self._streaming_adapter,
        )
        self._data_catalog = DataCatalog()
        self._metadata_service = MetadataService(catalog=self._data_catalog)
        self._schema_service = SchemaService()

        if self._config.enable_governance:
            self._governance = DataGovernance(
                catalog=self._data_catalog,
                metadata=self._metadata_service,
                schema=self._schema_service,
            )
            self._lineage_service = LineageService()
            self._quality_service = QualityService()
            self._retention_service = RetentionService()

        if self._config.enable_access_control:
            self._access_control = DataAccessControl()
            self._permission_manager = PermissionManager()
            if self._config.enable_audit:
                self._audit_service = AuditService()

        self._pipeline = UnifiedDataPipeline(
            connectivity=self._connectivity_adapter,
            normalization=self._normalization_adapter,
            streaming=self._streaming_adapter,
            data_lake=self._data_lake_adapter,
        )

        self._orchestrator = DataOrchestrator(
            access_control=self._access_control,
            catalog=self._data_catalog,
            pipeline=self._pipeline,
            audit=self._audit_service,
        )

        if self._config.enable_api_gateway:
            self._api_gateway = APIGateway(
                orchestrator=self._orchestrator,
                market_data=self._market_data_service,
                historical=self._historical_data_service,
                replay=self._replay_service,
                catalog=self._data_catalog,
                metadata=self._metadata_service,
                schema=self._schema_service,
                governance=self._governance,
                lineage=self._lineage_service,
                quality=self._quality_service,
            )

        self._sdk = DataSDK(api_gateway=self._api_gateway)

        self._gateway = DataGateway(
            orchestrator=self._orchestrator,
            pipeline=self._pipeline,
            sdk=self._sdk,
        )

        self._observability = PlatformObservability(
            metrics=self._metrics,
            telemetry=self._telemetry,
            diagnostics=self._diagnostics,
            health=self._health_checker,
        )

        if self._config.enable_control_plane:
            self._control_plane = DataControlPlane(
                health=self._health_checker,
                diagnostics=self._diagnostics,
                metrics=self._metrics,
                governance=self._governance,
                audit=self._audit_service,
            )

        self._initialized = True
        self._state = PlatformState.INITIALIZED
        logger.info("ICYQuant Unified Data Platform initialized")

    async def start(self) -> None:
        """Start the data platform."""
        if not self._initialized:
            await self.initialize()

        self._state = PlatformState.STARTING

        if self._connectivity_adapter:
            await self._connectivity_adapter.start()
        if self._normalization_adapter:
            await self._normalization_adapter.start()
        if self._data_lake_adapter:
            await self._data_lake_adapter.start()
        if self._streaming_adapter:
            await self._streaming_adapter.start()

        if self._pipeline:
            await self._pipeline.start()
        if self._orchestrator:
            await self._orchestrator.start()
        if self._gateway:
            await self._gateway.start()
        if self._api_gateway:
            await self._api_gateway.start()
        if self._control_plane:
            await self._control_plane.start()

        self._started_at = datetime.now(timezone.utc)
        self._state = PlatformState.RUNNING
        logger.info("ICYQuant Unified Data Platform started")

    async def stop(self) -> None:
        """Stop the data platform gracefully."""
        self._state = PlatformState.STOPPING

        if self._api_gateway:
            await self._api_gateway.stop()
        if self._gateway:
            await self._gateway.stop()
        if self._orchestrator:
            await self._orchestrator.stop()
        if self._pipeline:
            await self._pipeline.stop()
        if self._control_plane:
            await self._control_plane.stop()

        if self._streaming_adapter:
            await self._streaming_adapter.stop()
        if self._data_lake_adapter:
            await self._data_lake_adapter.stop()
        if self._normalization_adapter:
            await self._normalization_adapter.stop()
        if self._connectivity_adapter:
            await self._connectivity_adapter.stop()

        self._state = PlatformState.STOPPED
        logger.info("ICYQuant Unified Data Platform stopped")

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def state(self) -> PlatformState:
        return self._state

    @property
    def gateway(self) -> Optional[DataGateway]:
        return self._gateway

    @property
    def orchestrator(self) -> Optional[DataOrchestrator]:
        return self._orchestrator

    @property
    def api_gateway(self) -> Optional[APIGateway]:
        return self._api_gateway

    @property
    def sdk(self) -> Optional[DataSDK]:
        return self._sdk

    @property
    def control_plane(self) -> Optional[DataControlPlane]:
        return self._control_plane

    @property
    def catalog(self) -> Optional[DataCatalog]:
        return self._data_catalog

    @property
    def governance(self) -> Optional[DataGovernance]:
        return self._governance

    @property
    def metrics(self) -> Optional[DataPlatformMetrics]:
        return self._metrics

    def info(self) -> PlatformInfo:
        uptime = 0.0
        if self._started_at:
            uptime = (datetime.now(timezone.utc) - self._started_at).total_seconds()
        return PlatformInfo(
            name=self._config.name,
            version=self._config.version,
            state=self._state,
            uptime_seconds=uptime,
            total_requests=self._metrics.request_total if self._metrics else 0,
            datasets_registered=self._data_catalog.count if self._data_catalog else 0,
        )
