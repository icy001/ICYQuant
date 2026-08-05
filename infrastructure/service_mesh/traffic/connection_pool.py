"""Connection pool for ICYQuant Service Mesh.

Provides ``ConnectionPool`` for managing HTTP/HTTP2/gRPC/TCP
connections with configurable limits, idle timeouts, and keep-alive.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ConnectionProtocol(str, Enum):
    """Supported connection protocols."""

    HTTP = "http"
    HTTP2 = "http2"
    GRPC = "grpc"
    TCP = "tcp"


class PooledConnection:
    """A pooled connection."""

    def __init__(
        self,
        host: str,
        port: int,
        protocol: ConnectionProtocol = ConnectionProtocol.HTTP,
        conn_id: str = "",
    ) -> None:
        self.host = host
        self.port = port
        self.protocol = protocol
        self.conn_id = conn_id or f"conn-{id(self)}"
        self.created_at = time.monotonic()
        self.last_used = time.monotonic()
        self.idle_since: Optional[float] = None
        self.active = False
        self.total_requests = 0
        self.total_errors = 0

    @property
    def idle_time_s(self) -> float:
        if self.idle_since:
            return time.monotonic() - self.idle_since
        return 0.0

    def mark_used(self) -> None:
        self.last_used = time.monotonic()
        self.idle_since = None
        self.active = True

    def mark_idle(self) -> None:
        self.idle_since = time.monotonic()
        self.active = False


class ConnectionPool:
    """Manages connection pools per host."""

    def __init__(
        self,
        max_connections: int = 1024,
        max_idle_s: float = 60.0,
        keep_alive: bool = True,
        min_idle: int = 0,
    ) -> None:
        self._max_connections = max_connections
        self._max_idle_s = max_idle_s
        self._keep_alive = keep_alive
        self._min_idle = min_idle
        self._lock = threading.RLock()
        self._pools: Dict[str, List[PooledConnection]] = {}
        self._total_created = 0
        self._total_closed = 0
        self._total_requests = 0
        self._cleanup_count = 0

    def _get_pool_key(
        self, host: str, port: int
    ) -> str:
        return f"{host}:{port}"

    def acquire(
        self,
        host: str,
        port: int,
        protocol: ConnectionProtocol = ConnectionProtocol.HTTP,
    ) -> PooledConnection:
        """Acquire a connection from the pool."""
        with self._lock:
            key = self._get_pool_key(host, port)
            pool = self._pools.get(key)

            if pool:
                # Find an idle connection
                for conn in pool:
                    if not conn.active:
                        conn.mark_used()
                        self._total_requests += 1
                        conn.total_requests += 1
                        return conn

            # Create a new connection
            conn = PooledConnection(
                host, port, protocol
            )
            conn.mark_used()
            if key not in self._pools:
                self._pools[key] = []
            self._pools[key].append(conn)
            self._total_created += 1
            self._total_requests += 1
            return conn

    def release(
        self, conn: PooledConnection, error: bool = False
    ) -> None:
        """Release a connection back to the pool."""
        with self._lock:
            if error:
                conn.total_errors += 1
            conn.mark_idle()

    def close(self, conn: PooledConnection) -> None:
        """Close and remove a connection."""
        with self._lock:
            key = self._get_pool_key(
                conn.host, conn.port
            )
            pool = self._pools.get(key)
            if pool and conn in pool:
                pool.remove(conn)
                self._total_closed += 1

    def cleanup(self) -> Dict[str, int]:
        """Remove idle connections exceeding the timeout."""
        with self._lock:
            self._cleanup_count += 1
            closed = 0
            for key, pool in list(self._pools.items()):
                for conn in list(pool):
                    if conn.idle_time_s > self._max_idle_s:
                        pool.remove(conn)
                        self._total_closed += 1
                        closed += 1
                if not pool:
                    del self._pools[key]
            return {"closed": closed}

    def get_active_count(self) -> int:
        with self._lock:
            count = 0
            for pool in self._pools.values():
                count += sum(
                    1 for c in pool if c.active
                )
            return count

    def get_idle_count(self) -> int:
        with self._lock:
            count = 0
            for pool in self._pools.values():
                count += sum(
                    1 for c in pool if not c.active
                )
            return count

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            total = sum(
                len(p) for p in self._pools.values()
            )
            return {
                "pool_count": len(self._pools),
                "total_connections": total,
                "active_connections": self.get_active_count(),
                "idle_connections": self.get_idle_count(),
                "max_connections": self._max_connections,
                "total_created": self._total_created,
                "total_closed": self._total_closed,
                "total_requests": self._total_requests,
                "cleanup_count": self._cleanup_count,
            }