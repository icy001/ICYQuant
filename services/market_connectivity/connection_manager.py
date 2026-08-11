"""
Connection Manager — Manages the underlying transport connections
for exchange sessions, including connect/disconnect lifecycle,
protocol negotiation, and connection state tracking.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ConnectionState(str, Enum):
    """Connection lifecycle states."""
    CREATED = "created"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTING = "disconnecting"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    SUSPENDED = "suspended"


@dataclass
class ConnectionInfo:
    """Metadata for a single connection."""
    connection_id: str
    exchange_id: str
    protocol: str
    endpoint: str
    state: ConnectionState = ConnectionState.CREATED
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    connected_at: Optional[datetime] = None
    disconnected_at: Optional[datetime] = None
    last_activity: Optional[datetime] = None
    messages_sent: int = 0
    messages_received: int = 0
    errors: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class ConnectionManager:
    """
    Manages transport-level connections to exchanges.

    Handles the full lifecycle: create → connect → disconnect → reconnect,
    with protocol negotiation and state tracking.

    Usage::

        manager = ConnectionManager()
        await manager.initialize()
        conn = await manager.create_connection("binance", "websocket", "wss://...")
        await manager.connect(conn.connection_id)
        await manager.disconnect(conn.connection_id)
    """

    def __init__(self) -> None:
        self._connections: dict[str, ConnectionInfo] = {}
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the connection manager."""
        logger.info("ConnectionManager initialized.")

    # ---- Connection Lifecycle ----

    async def create_connection(
        self,
        exchange_id: str,
        protocol: str,
        endpoint: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> ConnectionInfo:
        """Create a new connection entry."""
        connection_id = f"{exchange_id}_{protocol}_{int(datetime.now(timezone.utc).timestamp() * 1000)}"
        conn = ConnectionInfo(
            connection_id=connection_id,
            exchange_id=exchange_id,
            protocol=protocol,
            endpoint=endpoint,
            metadata=metadata or {},
        )
        async with self._lock:
            self._connections[connection_id] = conn
        logger.info("Connection created: %s (%s://%s)", connection_id, protocol, exchange_id)
        return conn

    async def connect(self, connection_id: str) -> bool:
        """Establish a connection."""
        conn = self._connections.get(connection_id)
        if conn is None:
            logger.error("Connection not found: %s", connection_id)
            return False

        if conn.state == ConnectionState.CONNECTED:
            return True

        try:
            conn.state = ConnectionState.CONNECTING
            logger.info("Connecting: %s → %s", connection_id, conn.endpoint)
            await asyncio.sleep(0.01)  # placeholder for actual transport connect
            conn.state = ConnectionState.CONNECTED
            conn.connected_at = datetime.now(timezone.utc)
            conn.last_activity = datetime.now(timezone.utc)
            logger.info("Connected: %s", connection_id)
            return True
        except Exception:
            logger.exception("Failed to connect: %s", connection_id)
            conn.state = ConnectionState.ERROR
            conn.errors += 1
            return False

    async def disconnect(self, connection_id: str) -> bool:
        """Disconnect a connection."""
        conn = self._connections.get(connection_id)
        if conn is None:
            return False

        if conn.state == ConnectionState.DISCONNECTED:
            return True

        try:
            conn.state = ConnectionState.DISCONNECTING
            logger.info("Disconnecting: %s", connection_id)
            await asyncio.sleep(0.01)  # placeholder for actual transport close
            conn.state = ConnectionState.DISCONNECTED
            conn.disconnected_at = datetime.now(timezone.utc)
            logger.info("Disconnected: %s", connection_id)
            return True
        except Exception:
            logger.exception("Failed to disconnect: %s", connection_id)
            conn.state = ConnectionState.ERROR
            return False

    async def reconnect(self, connection_id: str) -> bool:
        """Reconnect a connection (disconnect + connect)."""
        await self.disconnect(connection_id)
        await asyncio.sleep(0.5)
        return await self.connect(connection_id)

    async def remove_connection(self, connection_id: str) -> bool:
        """Remove a connection from tracking."""
        async with self._lock:
            if connection_id in self._connections:
                del self._connections[connection_id]
                logger.info("Connection removed: %s", connection_id)
                return True
            return False

    # ---- Queries ----

    async def get_connection(self, connection_id: str) -> Optional[ConnectionInfo]:
        """Get a connection by ID."""
        return self._connections.get(connection_id)

    async def get_connections_for_exchange(
        self, exchange_id: str
    ) -> list[ConnectionInfo]:
        """Get all connections for a specific exchange."""
        return [
            c for c in self._connections.values()
            if c.exchange_id == exchange_id
        ]

    async def get_active_connections(self) -> list[ConnectionInfo]:
        """Get all currently connected connections."""
        return [
            c for c in self._connections.values()
            if c.state == ConnectionState.CONNECTED
        ]

    async def record_activity(self, connection_id: str) -> None:
        """Record activity on a connection."""
        conn = self._connections.get(connection_id)
        if conn:
            conn.last_activity = datetime.now(timezone.utc)

    async def record_message(self, connection_id: str, sent: bool = True) -> None:
        """Record a message sent or received."""
        conn = self._connections.get(connection_id)
        if conn:
            if sent:
                conn.messages_sent += 1
            else:
                conn.messages_received += 1
            conn.last_activity = datetime.now(timezone.utc)

    async def get_summary(self) -> dict[str, Any]:
        """Get summary of all connections."""
        total = len(self._connections)
        connected = sum(
            1 for c in self._connections.values()
            if c.state == ConnectionState.CONNECTED
        )
        return {
            "total_connections": total,
            "connected": connected,
            "disconnected": total - connected,
        }

    async def shutdown(self) -> None:
        """Disconnect all connections and shut down."""
        for conn_id in list(self._connections.keys()):
            await self.disconnect(conn_id)
        logger.info("ConnectionManager shut down.")
