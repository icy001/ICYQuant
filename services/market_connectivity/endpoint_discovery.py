"""
Endpoint Discovery — Dynamically discovers, health-checks, and selects
the best available endpoints for exchange connections.

Exchange → Endpoint List → Health Check → Best Endpoint
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class EndpointType(str, Enum):
    REST = "rest"
    WEBSOCKET = "websocket"
    GRPC = "grpc"
    FIX = "fix"
    TCP = "tcp"
    UDP = "udp"
    MULTICAST = "multicast"


class EndpointHealth(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class Endpoint:
    """A single exchange endpoint."""
    endpoint_id: str
    exchange_id: str
    endpoint_type: EndpointType
    url: str
    region: str = "global"
    priority: int = 100  # lower = higher priority
    health: EndpointHealth = EndpointHealth.UNKNOWN
    latency_ms: float = 0.0
    success_rate: float = 1.0
    last_checked: Optional[datetime] = None
    last_error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def score(self) -> float:
        """Calculate a composite score for endpoint selection (higher = better)."""
        health_score = {
            EndpointHealth.HEALTHY: 1.0,
            EndpointHealth.DEGRADED: 0.5,
            EndpointHealth.UNHEALTHY: 0.0,
            EndpointHealth.UNKNOWN: 0.7,
        }.get(self.health, 0.0)
        latency_score = max(0.0, 1.0 - self.latency_ms / 5000.0)  # normalize
        priority_score = max(0.0, 1.0 - self.priority / 200.0)
        return (health_score * 0.5 + self.success_rate * 0.2 + latency_score * 0.2 + priority_score * 0.1)


class EndpointDiscovery:
    """
    Dynamic endpoint discovery and selection.

    Maintains a pool of endpoints per exchange, performs health checks,
    and selects the optimal endpoint based on health, latency, and priority.

    Usage::

        discovery = EndpointDiscovery()
        await discovery.initialize()
        await discovery.register_endpoints("binance", [...])
        best = await discovery.get_best_endpoint("binance", EndpointType.WEBSOCKET)
    """

    def __init__(self) -> None:
        self._endpoints: dict[str, list[Endpoint]] = {}
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the endpoint discovery service."""
        logger.info("EndpointDiscovery initialized.")

    # ---- Registration ----

    async def register_endpoints(
        self, exchange_id: str, endpoints: list[Endpoint]
    ) -> None:
        """Register endpoints for an exchange."""
        async with self._lock:
            self._endpoints[exchange_id] = endpoints
        logger.info(
            "Registered %d endpoints for %s", len(endpoints), exchange_id
        )

    async def add_endpoint(self, endpoint: Endpoint) -> None:
        """Add a single endpoint for an exchange."""
        async with self._lock:
            if endpoint.exchange_id not in self._endpoints:
                self._endpoints[endpoint.exchange_id] = []
            self._endpoints[endpoint.exchange_id].append(endpoint)

    async def remove_endpoint(self, endpoint_id: str, exchange_id: str) -> bool:
        """Remove an endpoint."""
        async with self._lock:
            if exchange_id in self._endpoints:
                before = len(self._endpoints[exchange_id])
                self._endpoints[exchange_id] = [
                    e for e in self._endpoints[exchange_id]
                    if e.endpoint_id != endpoint_id
                ]
                return len(self._endpoints[exchange_id]) < before
            return False

    # ---- Selection ----

    async def get_best_endpoint(
        self, exchange_id: str, endpoint_type: Optional[EndpointType] = None
    ) -> Optional[Endpoint]:
        """Get the best (highest-scoring) endpoint for an exchange."""
        endpoints = self._endpoints.get(exchange_id, [])
        if not endpoints:
            return None

        if endpoint_type:
            endpoints = [e for e in endpoints if e.endpoint_type == endpoint_type]

        if not endpoints:
            return None

        healthy = [e for e in endpoints if e.health != EndpointHealth.UNHEALTHY]
        if not healthy:
            logger.warning("No healthy endpoints for %s, using best available", exchange_id)
            healthy = endpoints

        return max(healthy, key=lambda e: e.score)

    async def get_endpoints(
        self, exchange_id: str, endpoint_type: Optional[EndpointType] = None
    ) -> list[Endpoint]:
        """Get all endpoints for an exchange, optionally filtered by type."""
        endpoints = self._endpoints.get(exchange_id, [])
        if endpoint_type:
            endpoints = [e for e in endpoints if e.endpoint_type == endpoint_type]
        return sorted(endpoints, key=lambda e: e.score, reverse=True)

    async def get_all_endpoints(self) -> dict[str, list[Endpoint]]:
        """Get all registered endpoints across all exchanges."""
        return dict(self._endpoints)

    # ---- Health Checks ----

    async def update_health(
        self,
        exchange_id: str,
        endpoint_id: str,
        health: EndpointHealth,
        latency_ms: float = 0.0,
        error: str = "",
    ) -> bool:
        """Update the health status of an endpoint."""
        endpoints = self._endpoints.get(exchange_id, [])
        for ep in endpoints:
            if ep.endpoint_id == endpoint_id:
                ep.health = health
                ep.latency_ms = latency_ms
                ep.last_checked = datetime.now(timezone.utc)
                if error:
                    ep.last_error = error
                    ep.success_rate = max(0.0, ep.success_rate - 0.1)
                else:
                    ep.success_rate = min(1.0, ep.success_rate + 0.05)
                return True
        return False

    async def health_check_all(self, exchange_id: str) -> list[Endpoint]:
        """Perform health check on all endpoints for an exchange."""
        endpoints = self._endpoints.get(exchange_id, [])
        results = []
        for ep in endpoints:
            try:
                start = asyncio.get_event_loop().time()
                # Placeholder: actual health check would attempt connection
                await asyncio.sleep(0.001)
                latency = (asyncio.get_event_loop().time() - start) * 1000
                await self.update_health(
                    exchange_id, ep.endpoint_id,
                    EndpointHealth.HEALTHY, latency_ms=latency,
                )
            except Exception as e:
                await self.update_health(
                    exchange_id, ep.endpoint_id,
                    EndpointHealth.UNHEALTHY, error=str(e),
                )
            results.append(ep)
        return results

    # ---- Summary ----

    async def get_summary(self) -> dict[str, Any]:
        """Get summary of all endpoints."""
        total = sum(len(eps) for eps in self._endpoints.values())
        healthy = sum(
            sum(1 for e in eps if e.health == EndpointHealth.HEALTHY)
            for eps in self._endpoints.values()
        )
        return {
            "total_endpoints": total,
            "healthy_endpoints": healthy,
            "unhealthy_endpoints": total - healthy,
            "exchanges": list(self._endpoints.keys()),
        }
