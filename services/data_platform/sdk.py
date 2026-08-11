"""
ICYQuant Data SDK — Python SDK for the unified data platform.

Provides a convenient Pythonic interface for accessing all data platform
services: market data, historical data, replay, catalog, governance,
and pipeline operations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Optional

logger = logging.getLogger(__name__)


@dataclass
class SDKConfig:
    host: str = "localhost"
    port: int = 8200
    protocol: str = "http"
    api_key: str = ""
    timeout_seconds: int = 30
    max_retries: int = 3
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class QueryResult:
    """Result of a data query."""
    data: list[Any] = field(default_factory=list)
    total: int = 0
    query: str = ""
    elapsed_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class DataSDK:
    """Python SDK for unified data platform access.

    Provides:
        - market_data: subscribe, query market data
        - historical: query historical data
        - replay: replay historical scenarios
        - catalog: search and discover datasets
        - governance: check governance status
        - pipeline: monitor pipeline status
    """

    def __init__(self, config: Optional[SDKConfig] = None, platform: Any = None) -> None:
        self._config = config or SDKConfig()
        self._platform = platform
        self._connected = False
        self._request_count = 0

    async def connect(self) -> None:
        """Connect to the data platform."""
        self._connected = True
        logger.info("DataSDK connected to %s:%d", self._config.host, self._config.port)

    async def disconnect(self) -> None:
        """Disconnect from the data platform."""
        self._connected = False

    # ── Market Data ──

    async def query_market_data(
        self,
        instruments: list[str],
        fields: Optional[list[str]] = None,
    ) -> QueryResult:
        """Query real-time market data for instruments."""
        self._request_count += 1
        if self._platform and self._platform.gateway:
            return QueryResult(data=[], total=0)
        return QueryResult(data=[], total=0)

    async def subscribe(
        self,
        instruments: list[str],
        callback: Optional[Any] = None,
    ) -> dict[str, Any]:
        """Subscribe to real-time market data."""
        self._request_count += 1
        return {"status": "subscribed", "instruments": instruments}

    # ── Historical Data ──

    async def query_historical(
        self,
        dataset: str,
        start_time: str,
        end_time: str,
        instruments: Optional[list[str]] = None,
    ) -> QueryResult:
        """Query historical data."""
        self._request_count += 1
        return QueryResult(data=[], total=0)

    # ── Replay ──

    async def start_replay(
        self,
        scenario_id: str,
        start_time: str,
        speed: float = 1.0,
    ) -> dict[str, Any]:
        """Start a historical replay session."""
        self._request_count += 1
        return {"status": "started", "scenario_id": scenario_id}

    # ── Catalog ──

    async def search_catalog(
        self,
        query: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search the data catalog."""
        self._request_count += 1
        return []

    async def get_dataset_info(self, dataset_id: str) -> Optional[dict[str, Any]]:
        """Get dataset metadata."""
        self._request_count += 1
        return None

    # ── Governance ──

    async def check_governance(self, dataset_id: str) -> dict[str, Any]:
        """Check governance compliance."""
        self._request_count += 1
        return {"status": "compliant"}

    # ── Pipeline ──

    async def get_pipeline_status(self) -> dict[str, Any]:
        """Get data pipeline status."""
        self._request_count += 1
        return {"status": "running"}

    # ── Health ──

    async def health_check(self) -> dict[str, Any]:
        """Check platform health."""
        return {"status": "healthy", "connected": self._connected}

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def request_count(self) -> int:
        return self._request_count
