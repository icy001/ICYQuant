"""
ICYQuant Data Platform REST API.

Provides HTTP REST endpoints for market data, historical data, replay,
catalog, governance, and platform health.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class RESTConfig:
    host: str = "0.0.0.0"
    port: int = 8200
    prefix: str = "/api/v1/data"
    enable_cors: bool = True
    enable_docs: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class APIResponse:
    success: bool
    data: Any = None
    error: Optional[str] = None
    request_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class DataPlatformREST:
    """REST API endpoints for the data platform.

    Endpoints:
        GET    /market-data          — Query market data
        POST   /market-data/subscribe — Subscribe to market data
        GET    /historical           — Query historical data
        POST   /replay               — Start replay session
        GET    /catalog              — Search data catalog
        GET    /catalog/{id}         — Get dataset info
        GET    /governance/{id}      — Check governance status
        GET    /pipeline/status      — Pipeline health
        GET    /health               — Platform health
    """

    def __init__(self, platform: Any = None, config: Optional[RESTConfig] = None) -> None:
        self._platform = platform
        self._config = config or RESTConfig()
        self._request_count = 0

    async def query_market_data(self, params: dict[str, Any]) -> APIResponse:
        """GET /market-data"""
        self._request_count += 1
        return APIResponse(success=True, data={"data": [], "query": params})

    async def subscribe(self, body: dict[str, Any]) -> APIResponse:
        """POST /market-data/subscribe"""
        self._request_count += 1
        instruments = body.get("instruments", [])
        return APIResponse(success=True, data={"status": "subscribed", "instruments": instruments})

    async def query_historical(self, params: dict[str, Any]) -> APIResponse:
        """GET /historical"""
        self._request_count += 1
        return APIResponse(success=True, data={"data": [], "query": params})

    async def start_replay(self, body: dict[str, Any]) -> APIResponse:
        """POST /replay"""
        self._request_count += 1
        return APIResponse(success=True, data={"status": "started", "params": body})

    async def search_catalog(self, params: dict[str, Any]) -> APIResponse:
        """GET /catalog"""
        self._request_count += 1
        return APIResponse(success=True, data={"datasets": [], "total": 0})

    async def get_dataset_info(self, dataset_id: str) -> APIResponse:
        """GET /catalog/{id}"""
        self._request_count += 1
        if self._platform and self._platform.catalog:
            return APIResponse(success=True, data={"dataset_id": dataset_id})
        return APIResponse(success=False, error="Catalog not available")

    async def check_governance(self, dataset_id: str) -> APIResponse:
        """GET /governance/{id}"""
        self._request_count += 1
        return APIResponse(success=True, data={"status": "compliant", "dataset_id": dataset_id})

    async def pipeline_status(self) -> APIResponse:
        """GET /pipeline/status"""
        return APIResponse(success=True, data={"status": "running"})

    async def health(self) -> APIResponse:
        """GET /health"""
        info = {"status": "healthy"}
        if self._platform and hasattr(self._platform, 'get_info'):
            info = self._platform.get_info()
        return APIResponse(success=True, data=info)

    @property
    def total_requests(self) -> int:
        return self._request_count
