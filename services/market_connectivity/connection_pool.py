"""
Connection Pool — Reusable connection pool for transport connections
to reduce connection establishment overhead across exchanges.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from .connection_manager import ConnectionInfo, ConnectionManager, ConnectionState

logger = logging.getLogger(__name__)


@dataclass
class ConnectionPoolConfig:
    """Configuration for connection pool behavior."""
    pool_id: str = "default"
    min_connections: int = 1
    max_connections: int = 20
    idle_timeout_seconds: float = 300.0
    max_connection_age_seconds: float = 3600.0
    connection_timeout: float = 10.0
    health_check_interval: float = 30.0
    cleanup_interval: float = 60.0


@dataclass
class PooledConnection:
    """A connection in the pool with pool metadata."""
    connection: ConnectionInfo
    in_use: bool = False
    acquired_at: Optional[datetime] = None
    released_at: Optional[datetime] = None
    use_count: int = 0


class ConnectionPool:
    """
    Reusable connection pool for exchange transport connections.

    Manages a pool of ready-to-use connections, allowing callers
    to acquire, use, and release connections efficiently.

    Usage::

        pool = ConnectionPool(ConnectionPoolConfig(pool_id="main"))
        await pool.initialize()
        conn = await pool.acquire("binance", "websocket")
        # ... use connection ...
        await pool.release(conn)
    """

    def __init__(
        self,
        config: Optional[ConnectionPoolConfig] = None,
        connection_manager: Optional[ConnectionManager] = None,
    ) -> None:
        self.config = config or ConnectionPoolConfig()
        self._connection_manager = connection_manager or ConnectionManager()
        self._pools: dict[str, list[PooledConnection]] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None

    async def initialize(self) -> None:
        """Initialize the connection pool."""
        await self._connection_manager.initialize()
        logger.info("ConnectionPool '%s' initialized.", self.config.pool_id)

    async def start(self) -> None:
        """Start pool background tasks."""
        if self.config.cleanup_interval > 0:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop(self) -> None:
        """Stop the pool and drain connections."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
        await self.drain()
        await self._connection_manager.shutdown()
        logger.info("ConnectionPool '%s' stopped.", self.config.pool_id)

    # ---- Pool Operations ----

    async def acquire(
        self,
        exchange_id: str,
        protocol: str,
        endpoint: Optional[str] = None,
        **kwargs: Any,
    ) -> Optional[PooledConnection]:
        """Acquire a connection from the pool or create a new one."""
        pool_key = f"{exchange_id}_{protocol}"
        async with self._lock:
            if pool_key not in self._pools:
                self._pools[pool_key] = []

            # Try to find an idle connected connection
            for pooled in self._pools[pool_key]:
                if (
                    not pooled.in_use
                    and pooled.connection.state == ConnectionState.CONNECTED
                ):
                    pooled.in_use = True
                    pooled.acquired_at = datetime.now(timezone.utc)
                    pooled.use_count += 1
                    logger.debug("Acquired connection %s from pool", pooled.connection.connection_id)
                    return pooled

            # Create a new connection if under max
            if len(self._pools[pool_key]) < self.config.max_connections:
                ep = endpoint or f"{protocol}://{exchange_id}"
                conn = await self._connection_manager.create_connection(
                    exchange_id=exchange_id,
                    protocol=protocol,
                    endpoint=ep,
                )
                success = await self._connection_manager.connect(conn.connection_id)
                if success:
                    pooled = PooledConnection(
                        connection=conn,
                        in_use=True,
                        acquired_at=datetime.now(timezone.utc),
                        use_count=1,
                    )
                    self._pools[pool_key].append(pooled)
                    logger.debug("Created new connection %s for pool", conn.connection_id)
                    return pooled

        logger.warning("No connection available for %s/%s", exchange_id, protocol)
        return None

    async def release(self, pooled: PooledConnection) -> bool:
        """Release a connection back to the pool."""
        pool_key = f"{pooled.connection.exchange_id}_{pooled.connection.protocol}"
        async with self._lock:
            pooled.in_use = False
            pooled.released_at = datetime.now(timezone.utc)
            logger.debug("Released connection %s to pool", pooled.connection.connection_id)
            return True

    async def drain(self) -> None:
        """Drain all connections from the pool."""
        async with self._lock:
            for pool_key, pooled_conns in self._pools.items():
                for pooled in pooled_conns:
                    if pooled.connection.state == ConnectionState.CONNECTED:
                        await self._connection_manager.disconnect(pooled.connection.connection_id)
                pooled_conns.clear()
            self._pools.clear()
            logger.info("ConnectionPool drained.")

    # ---- Status ----

    async def get_status(self) -> dict[str, Any]:
        """Get pool status."""
        pools = {}
        total_idle = 0
        total_in_use = 0

        for key, pooled_conns in self._pools.items():
            idle = sum(1 for p in pooled_conns if not p.in_use)
            in_use = sum(1 for p in pooled_conns if p.in_use)
            total_idle += idle
            total_in_use += in_use
            pools[key] = {
                "total": len(pooled_conns),
                "idle": idle,
                "in_use": in_use,
            }

        return {
            "pool_id": self.config.pool_id,
            "total_idle": total_idle,
            "total_in_use": total_in_use,
            "config": {
                "min": self.config.min_connections,
                "max": self.config.max_connections,
            },
            "pools": pools,
        }

    async def _cleanup_loop(self) -> None:
        """Background cleanup of idle/expired connections."""
        while True:
            try:
                await asyncio.sleep(self.config.cleanup_interval)
                await self._cleanup()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Connection pool cleanup error")

    async def _cleanup(self) -> None:
        """Remove idle and expired pooled connections."""
        now = datetime.now(timezone.utc)
        async with self._lock:
            for pool_key, pooled_conns in list(self._pools.items()):
                for pooled in list(pooled_conns):
                    if pooled.in_use:
                        continue
                    # Check idle timeout
                    if pooled.released_at:
                        idle_seconds = (now - pooled.released_at).total_seconds()
                        if idle_seconds > self.config.idle_timeout_seconds:
                            pooled_conns.remove(pooled)
                            await self._connection_manager.disconnect(
                                pooled.connection.connection_id
                            )
                            logger.debug("Removed idle connection %s", pooled.connection.connection_id)
