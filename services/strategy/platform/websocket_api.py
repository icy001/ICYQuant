"""
WebSocket API — Real-time event streaming API for the Strategy Platform.

Provides WebSocket endpoints for strategy event streaming, runtime
monitoring, and real-time signal delivery.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class WSChannel(str, Enum):
    """WebSocket channel types."""
    STRATEGY_EVENTS = "strategy.events"
    SIGNAL_STREAM = "strategy.signals"
    RUNTIME_EVENTS = "strategy.runtime"
    ORDER_EVENTS = "strategy.orders"
    PLATFORM_EVENTS = "platform.events"
    AUDIT_STREAM = "platform.audit"


class WSMessageType(str, Enum):
    """WebSocket message types."""
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    EVENT = "event"
    HEARTBEAT = "heartbeat"
    ERROR = "error"
    ACK = "ack"


@dataclass
class WSConnection:
    """A WebSocket client connection."""
    connection_id: str
    channels: list[WSChannel] = field(default_factory=list)
    connected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_heartbeat: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class WSMessage:
    """A WebSocket message."""
    message_type: WSMessageType
    channel: Optional[WSChannel] = None
    payload: dict[str, Any] = field(default_factory=dict)
    message_id: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class StrategyWebSocketAPI:
    """
    WebSocket API for real-time strategy event streaming.

    Provides channels for strategy events, signal streams,
    runtime monitoring, and order events through persistent
    WebSocket connections.

    Channels:
        - strategy.events: Strategy lifecycle events
        - strategy.signals: Real-time signal stream
        - strategy.runtime: Runtime metrics and status
        - strategy.orders: Order lifecycle events
        - platform.events: Platform-level events
        - platform.audit: Audit record stream

    Usage::

        ws_api = StrategyWebSocketAPI(event_stream=stream)
        await ws_api.initialize()
        conn = await ws_api.connect("conn_001")
        await ws_api.subscribe("conn_001", WSChannel.STRATEGY_EVENTS)
        messages = await ws_api.receive("conn_001")
    """

    def __init__(self, event_stream: Any = None) -> None:
        self._event_stream = event_stream
        self._connections: dict[str, WSConnection] = {}
        self._message_queues: dict[str, asyncio.Queue] = {}
        self._counter: int = 0
        self._initialized: bool = False

    async def initialize(self) -> None:
        """Initialize the WebSocket API."""
        self._initialized = True
        logger.info("StrategyWebSocketAPI initialized.")

    async def stop(self) -> None:
        """Stop the WebSocket API and close all connections."""
        for conn_id in list(self._connections.keys()):
            await self.disconnect(conn_id)
        self._initialized = False
        logger.info("StrategyWebSocketAPI stopped.")

    # ---- Connection Management ----

    async def connect(self, connection_id: str, metadata: Optional[dict[str, Any]] = None) -> WSConnection:
        """Establish a new WebSocket connection."""
        if connection_id in self._connections:
            await self.disconnect(connection_id)

        conn = WSConnection(
            connection_id=connection_id,
            metadata=metadata or {},
        )
        self._connections[connection_id] = conn
        self._message_queues[connection_id] = asyncio.Queue(maxsize=1000)

        logger.info(f"WebSocket connected: {connection_id}")
        return conn

    async def disconnect(self, connection_id: str) -> bool:
        """Close a WebSocket connection."""
        conn = self._connections.pop(connection_id, None)
        self._message_queues.pop(connection_id, None)
        if conn:
            logger.info(f"WebSocket disconnected: {connection_id}")
            return True
        return False

    async def get_connection(self, connection_id: str) -> Optional[WSConnection]:
        """Get a connection by ID."""
        return self._connections.get(connection_id)

    # ---- Channel Subscription ----

    async def subscribe(self, connection_id: str, channel: WSChannel) -> bool:
        """Subscribe a connection to a channel."""
        conn = self._connections.get(connection_id)
        if not conn:
            return False
        if channel not in conn.channels:
            conn.channels.append(channel)
        logger.info(f"Subscribed {connection_id} to {channel.value}")
        return True

    async def unsubscribe(self, connection_id: str, channel: WSChannel) -> bool:
        """Unsubscribe a connection from a channel."""
        conn = self._connections.get(connection_id)
        if not conn:
            return False
        if channel in conn.channels:
            conn.channels.remove(channel)
        return True

    # ---- Message Delivery ----

    async def send(
        self,
        connection_id: str,
        message: WSMessage,
    ) -> bool:
        """Send a message to a specific connection."""
        queue = self._message_queues.get(connection_id)
        if not queue:
            return False
        try:
            queue.put_nowait(message)
            return True
        except asyncio.QueueFull:
            logger.warning(f"Message queue full for {connection_id}")
            return False

    async def broadcast(
        self,
        channel: WSChannel,
        payload: dict[str, Any],
    ) -> list[str]:
        """Broadcast a message to all connections subscribed to a channel."""
        delivered_to: list[str] = []
        message = WSMessage(
            message_type=WSMessageType.EVENT,
            channel=channel,
            payload=payload,
        )
        for conn_id, conn in self._connections.items():
            if channel in conn.channels:
                if await self.send(conn_id, message):
                    delivered_to.append(conn_id)
        return delivered_to

    async def receive(self, connection_id: str) -> Optional[WSMessage]:
        """Receive a message for a connection (non-blocking)."""
        queue = self._message_queues.get(connection_id)
        if not queue:
            return None
        try:
            return queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    async def receive_wait(self, connection_id: str, timeout: float = 30.0) -> Optional[WSMessage]:
        """Receive a message for a connection (blocking with timeout)."""
        queue = self._message_queues.get(connection_id)
        if not queue:
            return None
        try:
            return await asyncio.wait_for(queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    # ---- Heartbeat ----

    async def heartbeat(self, connection_id: str) -> None:
        """Update the heartbeat timestamp for a connection."""
        conn = self._connections.get(connection_id)
        if conn:
            conn.last_heartbeat = datetime.now(timezone.utc)

    async def get_stale_connections(self, max_idle_seconds: float = 60.0) -> list[str]:
        """Get connections that haven't sent a heartbeat recently."""
        stale: list[str] = []
        now = datetime.now(timezone.utc)
        for conn_id, conn in self._connections.items():
            if conn.last_heartbeat:
                idle = (now - conn.last_heartbeat).total_seconds()
                if idle > max_idle_seconds:
                    stale.append(conn_id)
        return stale

    # ---- Serialization ----

    @staticmethod
    def serialize_message(message: WSMessage) -> str:
        """Serialize a WSMessage to JSON string."""
        return json.dumps({
            "type": message.message_type.value,
            "channel": message.channel.value if message.channel else None,
            "payload": message.payload,
            "message_id": message.message_id,
            "timestamp": message.timestamp.isoformat(),
        })

    @staticmethod
    def deserialize_message(data: str) -> WSMessage:
        """Deserialize a JSON string to WSMessage."""
        obj = json.loads(data)
        return WSMessage(
            message_type=WSMessageType(obj.get("type", "event")),
            channel=WSChannel(obj["channel"]) if obj.get("channel") else None,
            payload=obj.get("payload", {}),
            message_id=obj.get("message_id"),
        )

    # ---- Health ----

    async def health_check(self) -> dict[str, Any]:
        """Check WebSocket API health."""
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "active_connections": len(self._connections),
            "channels": [c.value for c in WSChannel],
            "stale_connections": len(await self.get_stale_connections()),
        }
