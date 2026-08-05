"""Sidecar proxy for the Service Mesh.

Provides ``Sidecar`` for attaching a local proxy to each
business service, enabling transparent traffic management,
observability, and policy enforcement without service code
modification.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .context import MeshContext
from .events import MeshEvent, MeshEventPublisher
from .models import (
    ProxyConfig,
    ProxyProtocol,
    ProxyType,
    SidecarInstance,
    SidecarState,
)
from .exceptions import SidecarError, SidecarStartError

logger = logging.getLogger(__name__)


class Sidecar:
    """Sidecar proxy attached to a business service.

    Manages the local proxy lifecycle (created -> initializing
    -> running -> reloading -> draining -> stopped) and ensures
    transparent traffic interception.
    """

    def __init__(
        self,
        sidecar_id: str,
        service_name: str,
        namespace: str = "default",
        proxy_type: ProxyType = ProxyType.INTERNAL,
        context: Optional[MeshContext] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._context = context or MeshContext()
        self._instance = SidecarInstance(
            sidecar_id=sidecar_id,
            service_name=service_name,
            namespace=namespace,
            proxy_type=proxy_type,
            state=SidecarState.CREATED,
        )
        self._publisher: Optional[MeshEventPublisher] = None
        self._request_count = 0
        self._start_time: Optional[float] = None
        self._handlers: Dict[str, Callable] = {}
        self._context.register(f"sidecar_{sidecar_id}", self)

    def set_publisher(self, publisher: MeshEventPublisher) -> None:
        self._publisher = publisher

    @property
    def sidecar_id(self) -> str:
        return self._instance.sidecar_id

    @property
    def service_name(self) -> str:
        return self._instance.service_name

    @property
    def state(self) -> SidecarState:
        return self._instance.state

    @property
    def is_running(self) -> bool:
        return self._instance.state == SidecarState.RUNNING

    async def start(self) -> Dict[str, Any]:
        """Start the sidecar proxy."""
        with self._lock:
            self._instance.state = SidecarState.INITIALIZING

        if self._publisher:
            await self._publisher.publish(
                MeshEvent.SIDECAR_CREATED,
                {"sidecar_id": self._instance.sidecar_id},
            )

        try:
            await self._initialize_proxy()
            with self._lock:
                self._instance.state = SidecarState.RUNNING
                self._start_time = time.monotonic()
                self._instance.last_heartbeat = datetime.utcnow()

            if self._publisher:
                await self._publisher.publish(
                    MeshEvent.SIDECAR_STARTED,
                    {"sidecar_id": self._instance.sidecar_id},
                )

            logger.info(
                "Sidecar %s started for service %s.",
                self._instance.sidecar_id,
                self._instance.service_name,
            )
            return {"success": True, "state": "running"}
        except Exception as exc:
            with self._lock:
                self._instance.state = SidecarState.ERROR
                self._instance.error_count += 1
            if self._publisher:
                await self._publisher.publish(
                    MeshEvent.SIDECAR_ERROR,
                    {
                        "sidecar_id": self._instance.sidecar_id,
                        "error": str(exc),
                    },
                )
            raise SidecarStartError(str(exc))

    async def stop(self) -> Dict[str, Any]:
        """Stop the sidecar proxy."""
        with self._lock:
            self._instance.state = SidecarState.DRAINING

        logger.info(
            "Sidecar %s draining for service %s.",
            self._instance.sidecar_id,
            self._instance.service_name,
        )

        await self._drain_connections()

        with self._lock:
            self._instance.state = SidecarState.STOPPED

        if self._publisher:
            await self._publisher.publish(
                MeshEvent.SIDECAR_STOPPED,
                {"sidecar_id": self._instance.sidecar_id},
            )

        logger.info(
            "Sidecar %s stopped.",
            self._instance.sidecar_id,
        )
        return {"success": True, "state": "stopped"}

    async def reload(
        self, config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Hot-reload sidecar configuration."""
        with self._lock:
            self._instance.state = SidecarState.RELOADING

        if config:
            with self._lock:
                self._instance.config.update(config)

        await asyncio.sleep(0.01)

        with self._lock:
            self._instance.state = SidecarState.RUNNING
            self._instance.last_heartbeat = datetime.utcnow()

        if self._publisher:
            await self._publisher.publish(
                MeshEvent.PROXY_RELOADED,
                {
                    "sidecar_id": self._instance.sidecar_id,
                    "config_updated": bool(config),
                },
            )

        return {
            "success": True,
            "state": "running",
            "config_updated": bool(config),
        }

    async def heartbeat(self) -> Dict[str, Any]:
        """Send sidecar heartbeat."""
        with self._lock:
            self._instance.last_heartbeat = datetime.utcnow()
        return {"success": True, "sidecar_id": self._instance.sidecar_id}

    def handle_request(
        self,
        method: str,
        path: str,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Handle an incoming request through the sidecar."""
        with self._lock:
            self._request_count += 1

        handler = self._handlers.get(method)
        if handler:
            return handler(method, path, headers)

        return {
            "status": 200,
            "body": {
                "sidecar_id": self._instance.sidecar_id,
                "service": self._instance.service_name,
                "method": method,
                "path": path,
            },
        }

    def register_handler(
        self, method: str, handler: Callable
    ) -> None:
        self._handlers[method] = handler

    async def _initialize_proxy(self) -> None:
        """Initialize the proxy. Override for custom behavior."""
        await asyncio.sleep(0.001)

    async def _drain_connections(self) -> None:
        """Drain active connections before shutdown."""
        await asyncio.sleep(0.01)

    def get_instance(self) -> SidecarInstance:
        with self._lock:
            return self._instance

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "sidecar_id": self._instance.sidecar_id,
                "service_name": self._instance.service_name,
                "state": self._instance.state.value,
                "proxy_type": self._instance.proxy_type.value,
                "request_count": self._request_count,
                "uptime_s": (
                    time.monotonic() - self._start_time
                    if self._start_time
                    else 0
                ),
                "error_count": self._instance.error_count,
            }

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"Sidecar(id={self._instance.sidecar_id}, "
                f"service={self._instance.service_name}, "
                f"state={self._instance.state.value})"
            )
