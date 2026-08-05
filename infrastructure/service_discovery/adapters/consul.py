"""Consul registry adapter (stub with graceful fallback).

Provides ``ConsulAdapter``, a stub implementation of
``RegistryAdapter`` targeting HashiCorp Consul as a backend. The
adapter attempts to connect using ``python-consul`` or ``aiohttp``
when available and falls back gracefully when the backend libraries
are absent.

Consul service registration format::

    {
        "Name": "<service_name>",
        "ID": "<instance_id>",
        "Address": "<host>",
        "Port": <port>,
        "Tags": ["<namespace>", "version=<version>"],
        "Meta": { ... metadata ... },
        "Check": { ... health check definition ... }
    }

Service discovery queries Consul's catalog and health endpoints
scoped by namespace tags and version metadata.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ..exceptions import AdapterConnectionError
from ..instance import ServiceInstance
from ..service import Service
from .base import RegistryAdapter

logger = logging.getLogger(__name__)


class ConsulAdapter(RegistryAdapter):
    """Consul-backed registry adapter (stub).

    Args:
        host: Consul agent host.
        port: Consul agent HTTP port.
        token: Optional ACL token.

    The adapter is a stub. ``connect`` attempts to construct a client
    using ``consul`` (python-consul) or ``aiohttp`` and falls back
    gracefully when unavailable. All data operations raise
    ``AdapterConnectionError`` when the adapter is not connected.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 8500,
        token: Optional[str] = None,
    ) -> None:
        self._host = host or "localhost"
        self._port = int(port) if port else 8500
        self._token = token
        self._client: Any = None
        self._connected: bool = False

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        return self._port

    async def connect(self) -> None:
        """Attempt to connect to Consul, falling back gracefully."""
        try:
            try:
                import consul  # type: ignore
            except ImportError:
                consul = None

            if consul is not None:
                self._client = consul.Consul(
                    host=self._host, port=self._port, token=self._token
                )
                self._connected = True
                logger.info(
                    "ConsulAdapter connected via python-consul to %s:%s.",
                    self._host,
                    self._port,
                )
                return

            try:
                import aiohttp  # type: ignore  # noqa: F401
            except ImportError:
                aiohttp = None

            if aiohttp is not None:
                # HTTP session is created lazily on first request; mark
                # the adapter as connected and avoid leaking a session.
                self._client = None
                self._connected = True
                logger.info(
                    "ConsulAdapter connected via aiohttp to %s:%s.",
                    self._host,
                    self._port,
                )
                return

            logger.warning(
                "ConsulAdapter could not connect: neither 'python-consul' nor "
                "'aiohttp' is installed; adapter remains disconnected."
            )
            self._connected = False
        except Exception as e:  # pragma: no cover - depends on environment
            logger.warning("ConsulAdapter connection failed: %s", e)
            self._connected = False

    async def disconnect(self) -> None:
        self._client = None
        self._connected = False
        logger.debug("ConsulAdapter disconnected.")

    def is_connected(self) -> bool:
        return self._connected

    def _ensure_connected(self) -> None:
        if not self._connected:
            raise AdapterConnectionError(
                "ConsulAdapter is not connected; call connect() first."
            )

    async def register(self, instance: ServiceInstance) -> None:
        self._ensure_connected()
        raise NotImplementedError(
            "ConsulAdapter.register is not yet implemented."
        )

    async def deregister(self, service_name: str, instance_id: str) -> None:
        self._ensure_connected()
        raise NotImplementedError(
            "ConsulAdapter.deregister is not yet implemented."
        )

    async def discover(
        self,
        service_name: str,
        namespace: str = "default",
        version: str = None,
    ) -> List[ServiceInstance]:
        self._ensure_connected()
        raise NotImplementedError(
            "ConsulAdapter.discover is not yet implemented."
        )

    async def get_service(
        self, service_name: str, namespace: str = "default"
    ) -> Optional[Service]:
        self._ensure_connected()
        raise NotImplementedError(
            "ConsulAdapter.get_service is not yet implemented."
        )

    async def list_services(self, namespace: str = "default") -> List[Service]:
        self._ensure_connected()
        raise NotImplementedError(
            "ConsulAdapter.list_services is not yet implemented."
        )

    async def heartbeat(self, service_name: str, instance_id: str) -> None:
        self._ensure_connected()
        raise NotImplementedError(
            "ConsulAdapter.heartbeat is not yet implemented."
        )

    async def update_instance(
        self,
        service_name: str,
        instance_id: str,
        updates: Dict[str, Any],
    ) -> None:
        self._ensure_connected()
        raise NotImplementedError(
            "ConsulAdapter.update_instance is not yet implemented."
        )

    def get_stats(self) -> Dict[str, Any]:
        return {
            "adapter_type": "consul",
            "connected": self._connected,
            "host": self._host,
            "port": self._port,
        }

    def __repr__(self) -> str:
        return f"ConsulAdapter(connected={self._connected})"
