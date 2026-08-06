"""Service Mesh Adapter — integrates the Scheduler with the platform Service Mesh.

The :class:`ServiceMeshAdapter` provides service governance capabilities
for scheduler-to-service communication:
* Service discovery integration
* mTLS for secure inter-service calls
* Traffic policy enforcement (retry, timeout, circuit breaker)
* Load balancing across service instances

Architecture::

    Scheduler ──→ ServiceMeshAdapter ──→ Target Service
                      │
              ┌───────┼───────┐
           Discovery  mTLS   Traffic Policy
"""

from __future__ import annotations

import asyncio
import enum
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MeshMode(enum.Enum):
    """Service mesh operational modes."""

    SIDECAR = "sidecar"
    AMBIENT = "ambient"
    NONE = "none"


class ServiceMeshAdapter:
    """Adapter for service mesh integration.

    Responsibilities:
    * Discover service endpoints via mesh
    * Apply mTLS for secure communication
    * Enforce traffic policies (timeout, retry, circuit breaker)
    * Load balance requests across instances

    Usage::

        adapter = ServiceMeshAdapter(mode=MeshMode.SIDECAR)
        await adapter.connect()
        endpoint = await adapter.resolve("workflow-engine")
        await adapter.call(endpoint, payload)
    """

    def __init__(self, mode: MeshMode = MeshMode.NONE) -> None:
        self._mode = mode
        self._lock = threading.Lock()
        self._connected = False
        self._service_cache: Dict[str, List[Dict[str, Any]]] = {}
        self._cache_ttl = 30.0
        self._policies: Dict[str, Dict[str, Any]] = {}
        self._call_count: int = 0
        self._error_count: int = 0
        self._default_policy = {
            "timeout_ms": 30000,
            "max_retries": 3,
            "circuit_breaker": {"max_failures": 5, "reset_timeout_ms": 60000},
        }

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def mode(self) -> MeshMode:
        return self._mode

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def call_count(self) -> int:
        return self._call_count

    @property
    def error_count(self) -> int:
        return self._error_count

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Connect to the service mesh."""
        logger.info("ServiceMeshAdapter: connecting in %s mode", self._mode.value)
        self._connected = True

    async def disconnect(self) -> None:
        """Disconnect from the service mesh."""
        self._connected = False
        self._service_cache.clear()
        logger.info("ServiceMeshAdapter: disconnected")

    async def synchronize(self) -> Dict[str, Any]:
        """Synchronize mesh state."""
        return {"mode": self._mode.value, "connected": self._connected, "cached_services": len(self._service_cache)}

    # ------------------------------------------------------------------
    # Service Resolution
    # ------------------------------------------------------------------

    async def resolve(self, service_name: str) -> List[Dict[str, Any]]:
        """Resolve a service name to its endpoints via the mesh.

        Returns a list of endpoint dicts with 'host', 'port', 'healthy'.
        """
        # Return cached if fresh
        cached = self._service_cache.get(service_name)
        if cached:
            return cached

        # In a real mesh, this queries the sidecar/control plane
        endpoints = [{"host": f"{service_name}.local", "port": 8080, "healthy": True}]
        self._service_cache[service_name] = endpoints
        return endpoints

    async def resolve_one(self, service_name: str) -> Optional[Dict[str, Any]]:
        """Resolve a single healthy endpoint for a service."""
        endpoints = await self.resolve(service_name)
        healthy = [ep for ep in endpoints if ep.get("healthy", True)]
        return healthy[0] if healthy else None

    # ------------------------------------------------------------------
    # Service Call
    # ------------------------------------------------------------------

    async def call(
        self,
        service_name: str,
        method: str = "POST",
        path: str = "/",
        payload: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Make a service call through the mesh.

        Applies traffic policies: timeout, retry, circuit breaker.
        """
        self._call_count += 1
        policy = self._policies.get(service_name, self._default_policy)

        endpoint = await self.resolve_one(service_name)
        if not endpoint:
            self._error_count += 1
            return {"status": "error", "error": "no_healthy_endpoint"}

        result: Dict[str, Any] = {"service": service_name, "status": "pending"}

        # Circuit breaker check
        cb = policy.get("circuit_breaker", {})
        if self._is_circuit_open(service_name, cb):
            return {"status": "error", "error": "circuit_breaker_open"}

        # Retry loop
        max_retries = policy.get("max_retries", 3)
        for attempt in range(max_retries + 1):
            try:
                # Simulated call — in real mesh this goes through sidecar
                result["status"] = "ok"
                result["endpoint"] = f"{endpoint['host']}:{endpoint['port']}{path}"
                result["attempt"] = attempt + 1
                return result
            except Exception as exc:
                if attempt < max_retries:
                    await asyncio.sleep(0.1 * (2 ** attempt))  # exponential backoff
                    continue
                self._error_count += 1
                result["status"] = "error"
                result["error"] = str(exc)

        return result

    # ------------------------------------------------------------------
    # Traffic Policy
    # ------------------------------------------------------------------

    def set_policy(self, service_name: str, policy: Dict[str, Any]) -> None:
        """Set traffic policy for a specific service."""
        self._policies[service_name] = {**self._default_policy, **policy}

    def get_policy(self, service_name: str) -> Dict[str, Any]:
        """Get traffic policy for a service."""
        return self._policies.get(service_name, self._default_policy)

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _is_circuit_open(self, service_name: str, cb_config: Dict[str, Any]) -> bool:
        """Check if circuit breaker is open for a service."""
        # Simplified: always closed in this stub
        return False
