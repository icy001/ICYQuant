"""Proxy framework for the Service Mesh.

Provides ``MeshProxy`` as a unified proxy interface for HTTP,
gRPC, and TCP protocols, handling request interception, load
balancing, and response processing.
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
from .models import ProxyConfig, ProxyProtocol

logger = logging.getLogger(__name__)


class MeshProxy:
    """Unified proxy interface for mesh traffic."""

    def __init__(
        self,
        config: Optional[ProxyConfig] = None,
        context: Optional[MeshContext] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._context = context or MeshContext()
        self._config = config or ProxyConfig()
        self._publisher: Optional[MeshEventPublisher] = None
        self._request_count = 0
        self._response_count = 0
        self._error_count = 0
        self._load_balancer_index = 0
        self._upstreams: List[Dict[str, Any]] = []
        self._middleware: List[Callable] = []
        self._running = False
        self._start_time: Optional[float] = None

        self._context.register("proxy", self)

    def set_publisher(self, publisher: MeshEventPublisher) -> None:
        self._publisher = publisher

    async def start(self) -> Dict[str, Any]:
        with self._lock:
            self._running = True
            self._start_time = time.monotonic()
        logger.info(
            "Mesh proxy started on %s:%d (%s).",
            self._config.listen_host,
            self._config.listen_port,
            self._config.protocol.value,
        )
        return {"success": True}

    async def stop(self) -> Dict[str, Any]:
        with self._lock:
            self._running = False
        logger.info("Mesh proxy stopped.")
        return {"success": True}

    @property
    def is_running(self) -> bool:
        return self._running

    def add_upstream(
        self,
        host: str,
        port: int,
        weight: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        with self._lock:
            self._upstreams.append({
                "host": host,
                "port": port,
                "weight": weight,
                "metadata": metadata or {},
                "healthy": True,
            })

    def remove_upstream(self, host: str, port: int) -> bool:
        with self._lock:
            for i, up in enumerate(self._upstreams):
                if up["host"] == host and up["port"] == port:
                    self._upstreams.pop(i)
                    return True
        return False

    def set_upstream_health(
        self, host: str, port: int, healthy: bool
    ) -> None:
        with self._lock:
            for up in self._upstreams:
                if up["host"] == host and up["port"] == port:
                    up["healthy"] = healthy

    def add_middleware(self, middleware: Callable) -> None:
        self._middleware.append(middleware)

    async def handle_request(
        self,
        method: str,
        path: str,
        headers: Optional[Dict[str, str]] = None,
        body: Any = None,
    ) -> Dict[str, Any]:
        """Handle an incoming proxy request."""
        with self._lock:
            self._request_count += 1

        start = time.monotonic()
        try:
            upstream = self._select_upstream()
            if upstream is None:
                return {
                    "status": 503,
                    "body": {"error": "No healthy upstream"},
                }

            result = await self._dispatch(
                upstream, method, path, headers, body
            )
            with self._lock:
                self._response_count += 1
            return result
        except Exception as exc:
            with self._lock:
                self._error_count += 1
            logger.error("Proxy request failed: %s", exc)
            return {
                "status": 502,
                "body": {"error": str(exc)},
            }
        finally:
            duration = time.monotonic() - start
            if self._publisher and duration > 0:
                await self._publisher.publish(
                    MeshEvent.PROXY_RELOADED,
                    {
                        "method": method,
                        "path": path,
                        "duration_s": duration,
                    },
                )

    async def handle_response(
        self,
        response: Dict[str, Any],
        upstream: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Process and enhance an outgoing response."""
        response["_proxy_processed"] = True
        response["_timestamp"] = datetime.utcnow().isoformat()
        if upstream:
            response["_upstream"] = f"{upstream['host']}:{upstream['port']}"
        return response

    def _select_upstream(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            healthy = [u for u in self._upstreams if u["healthy"]]
            if not healthy:
                return None
            total_weight = sum(u["weight"] for u in healthy)
            if total_weight <= 0:
                return healthy[self._load_balancer_index % len(healthy)]
            self._load_balancer_index = (
                self._load_balancer_index + 1
            ) % len(healthy)
            return healthy[self._load_balancer_index]

    async def _dispatch(
        self,
        upstream: Dict[str, Any],
        method: str,
        path: str,
        headers: Optional[Dict[str, str]] = None,
        body: Any = None,
    ) -> Dict[str, Any]:
        # Apply middleware chain
        for mw in self._middleware:
            result = mw(method, path, headers, body)
            if asyncio.iscoroutine(result):
                result = await result
            if result is not None:
                if not result.get("success", True):
                    return result

        return {
            "status": 200,
            "body": {
                "upstream": f"{upstream['host']}:{upstream['port']}",
                "method": method,
                "path": path,
                "proxied": True,
            },
            "headers": headers or {},
        }

    def configure(self, config: ProxyConfig) -> None:
        with self._lock:
            self._config = config

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "running": self._running,
                "config": self._config.to_dict(),
                "request_count": self._request_count,
                "response_count": self._response_count,
                "error_count": self._error_count,
                "upstream_count": len(self._upstreams),
                "healthy_upstreams": sum(
                    1 for u in self._upstreams if u["healthy"]
                ),
                "middleware_count": len(self._middleware),
                "uptime_s": (
                    time.monotonic() - self._start_time
                    if self._start_time
                    else 0
                ),
            }

    def clear(self) -> None:
        with self._lock:
            self._upstreams.clear()
            self._middleware.clear()
            self._request_count = 0
            self._response_count = 0
            self._error_count = 0
            self._load_balancer_index = 0

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"MeshProxy(running={self._running}, "
                f"upstreams={len(self._upstreams)}, "
                f"requests={self._request_count})"
            )
