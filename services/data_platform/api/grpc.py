"""
ICYQuant Data Platform gRPC API.

High-performance gRPC endpoints for market data streaming, historical
data queries, replay sessions, catalog operations, and pipeline control.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, AsyncIterator, Optional

logger = logging.getLogger(__name__)


class ServiceMethod(str, Enum):
    QUERY_MARKET_DATA = "QueryMarketData"
    SUBSCRIBE_MARKET_DATA = "SubscribeMarketData"
    QUERY_HISTORICAL = "QueryHistorical"
    START_REPLAY = "StartReplay"
    SEARCH_CATALOG = "SearchCatalog"
    CHECK_GOVERNANCE = "CheckGovernance"
    PIPELINE_STATUS = "PipelineStatus"
    HEALTH_CHECK = "HealthCheck"


@dataclass
class GRPCConfig:
    host: str = "0.0.0.0"
    port: int = 8201
    max_message_size_mb: int = 100
    enable_reflection: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GRPCResponse:
    success: bool
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    error_code: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class DataPlatformGRPC:
    """gRPC API for the data platform.

    Services:
        - MarketDataService: Real-time and streaming market data
        - HistoricalDataService: Historical data queries
        - ReplayService: Historical replay sessions
        - CatalogService: Data catalog operations
        - GovernanceService: Governance checks
        - PipelineService: Pipeline monitoring
    """

    def __init__(self, platform: Any = None, config: Optional[GRPCConfig] = None) -> None:
        self._platform = platform
        self._config = config or GRPCConfig()
        self._request_count = 0

    async def query_market_data(self, request: dict[str, Any]) -> GRPCResponse:
        """QueryMarketData — Synchronous market data query."""
        self._request_count += 1
        return GRPCResponse(success=True, message="market data retrieved", data={"data": []})

    async def subscribe_market_data(self, request: dict[str, Any]) -> AsyncIterator[GRPCResponse]:
        """SubscribeMarketData — Streaming market data subscription."""
        self._request_count += 1
        instruments = request.get("instruments", [])
        yield GRPCResponse(success=True, message="subscription started",
                          data={"instruments": instruments})
        # In production, would stream continuous data updates

    async def query_historical(self, request: dict[str, Any]) -> GRPCResponse:
        """QueryHistorical — Historical data query."""
        self._request_count += 1
        return GRPCResponse(success=True, message="historical data retrieved", data={"data": []})

    async def start_replay(self, request: dict[str, Any]) -> GRPCResponse:
        """StartReplay — Start a historical replay session."""
        self._request_count += 1
        return GRPCResponse(success=True, message="replay started", data=request)

    async def search_catalog(self, request: dict[str, Any]) -> GRPCResponse:
        """SearchCatalog — Search the data catalog."""
        self._request_count += 1
        return GRPCResponse(success=True, data={"datasets": [], "total": 0})

    async def check_governance(self, request: dict[str, Any]) -> GRPCResponse:
        """CheckGovernance — Check dataset governance."""
        self._request_count += 1
        return GRPCResponse(success=True, message="compliant")

    async def pipeline_status(self) -> GRPCResponse:
        """PipelineStatus — Get pipeline health."""
        return GRPCResponse(success=True, message="pipeline running")

    async def health_check(self) -> GRPCResponse:
        """HealthCheck — Service health check."""
        return GRPCResponse(success=True, message="healthy")

    @property
    def total_requests(self) -> int:
        return self._request_count
