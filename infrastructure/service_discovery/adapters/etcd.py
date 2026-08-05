"""Etcd registry adapter (stub with graceful fallback).

Provides ``EtcdAdapter``, a stub implementation of ``RegistryAdapter``
targeting etcd as a backend. The adapter attempts to connect using
``etcd3`` or ``aiohttp`` when available and falls back gracefully
when the backend libraries are absent.

Etcd key structure::

    {prefix}{namespace}/{service_name}/{instance_id}

For example::

    /icyquant/services/production/market-data/instance-1
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ..exceptions import AdapterConnectionError
from ..instance import ServiceInstance
from ..service import Service
from .base import RegistryAdapter

logger = logging.getLogger(__name__)


class EtcdAdapter(RegistryAdapter):
    """Etcd-backed registry adapter (stub).

    Args:
        endpoints: List of etcd endpoint URLs.
        prefix: Key prefix used for all service records.

    The adapter is a stub. ``connect`` attempts to construct a client
    using ``etcd3`` (or ``aiohttp``) and falls back gracefully when
    unavailable. All data operations raise ``AdapterConnectionError``
    when the adapter is not connected.
    """

    def __init__(
        self,
        endpoints: Optional[List[str]] = None,
        prefix: str = "/icyquant/services/",
    ) -> None:
        self._endpoints = (
            list(endpoints) if endpoints else ["http://localhost:2379"]
        )
        self._prefix = prefix or "/icyquant/services/"
        self._client: Any = None
        self._connected: bool = False

    @property
    def endpoints(self) -> List[str]:
        return list(self._endpoints)

    @property
    def prefix(self) -> str:
        return self._prefix

    async def connect(self) -> None:
        """Attempt to connect to etcd, falling back gracefully."""
        try:
            try:
                import etcd3  # type: ignore
            except ImportError:
                etcd3 = None

            if etcd3 is not None:
                endpoint = (
                    self._endpoints[0] if self._endpoints else "localhost:2379"
                )
                cleaned = endpoint.replace("http://", "").replace("https://", "")
                host, _, port_str = cleaned.partition(":")
                self._client = etcd3.client(
                    host=host or "localhost",
                    port=int(port_str) if port_str else 2379,
                )
                self._connected = True
                logger.info("EtcdAdapter connected via etcd3 to %s.", endpoint)
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
                    "EtcdAdapter connected via aiohttp to %s.", self._endpoints
                )
                return

            logger.warning(
                "EtcdAdapter could not connect: neither 'etcd3' nor 'aiohttp' "
                "is installed; adapter remains disconnected."
            )
            self._connected = False
        except Exception as e:  # pragma: no cover - depends on environment
            logger.warning("EtcdAdapter connection failed: %s", e)
            self._connected = False

    async def disconnect(self) -> None:
        self._client = None
        self._connected = False
        logger.debug("EtcdAdapter disconnected.")

    def is_connected(self) -> bool:
        return self._connected

    def _ensure_connected(self) -> None:
        if not self._connected:
            raise AdapterConnectionError(
                "EtcdAdapter is not connected; call connect() first."
            )

    async def register(self, instance: ServiceInstance) -> None:
        self._ensure_connected()
        raise NotImplementedError("EtcdAdapter.register is not yet implemented.")

    async def deregister(self, service_name: str, instance_id: str) -> None:
        self._ensure_connected()
        raise NotImplementedError(
            "EtcdAdapter.deregister is not yet implemented."
        )

    async def discover(
        self,
        service_name: str,
        namespace: str = "default",
        version: str = None,
    ) -> List[ServiceInstance]:
        self._ensure_connected()
        raise NotImplementedError("EtcdAdapter.discover is not yet implemented.")

    async def get_service(
        self, service_name: str, namespace: str = "default"
    ) -> Optional[Service]:
        self._ensure_connected()
        raise NotImplementedError(
            "EtcdAdapter.get_service is not yet implemented."
        )

    async def list_services(self, namespace: str = "default") -> List[Service]:
        self._ensure_connected()
        raise NotImplementedError(
            "EtcdAdapter.list_services is not yet implemented."
        )

    async def heartbeat(self, service_name: str, instance_id: str) -> None:
        self._ensure_connected()
        raise NotImplementedError(
            "EtcdAdapter.heartbeat is not yet implemented."
        )

    async def update_instance(
        self,
        service_name: str,
        instance_id: str,
        updates: Dict[str, Any],
    ) -> None:
        self._ensure_connected()
        raise NotImplementedError(
            "EtcdAdapter.update_instance is not yet implemented."
        )

    def get_stats(self) -> Dict[str, Any]:
        return {
            "adapter_type": "etcd",
            "connected": self._connected,
            "endpoints": list(self._endpoints),
            "prefix": self._prefix,
        }

    def __repr__(self) -> str:
        return f"EtcdAdapter(connected={self._connected})"
