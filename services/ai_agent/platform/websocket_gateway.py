"""WebSocket Gateway — real-time streaming gateway for the AI Platform.

The WebSocketGateway provides real-time, bidirectional communication for
streaming AI responses, live agent reasoning visualization, and event-driven
updates. It supports multiple concurrent client connections with per-session
channel management.

Capabilities:
    - Real-time chat streaming
    - Agent reasoning visualization
    - Live event broadcasting
    - Per-user channel subscriptions
    - Connection lifecycle management
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class WSMessageType(str, Enum):
    """WebSocket message types."""
    CHAT_REQUEST = "chat_request"
    CHAT_STREAM = "chat_stream"
    CHAT_COMPLETE = "chat_complete"
    AGENT_EVENT = "agent_event"
    REASONING_UPDATE = "reasoning_update"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    ERROR = "error"
    PING = "ping"
    PONG = "pong"


@dataclass
class WSConnection:
    """A WebSocket client connection."""
    connection_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    user_id: str = ""
    session_id: str = ""
    channels: Set[str] = field(default_factory=set)
    connected_at: float = field(default_factory=time.monotonic)
    last_active: float = field(default_factory=time.monotonic)


@dataclass
class WSMessage:
    """A WebSocket message."""
    msg_type: WSMessageType
    data: Any = None
    connection_id: str = ""
    timestamp: float = field(default_factory=time.monotonic)


class WebSocketGateway:
    """Real-time WebSocket streaming gateway for the AI Platform.

    Provides bidirectional streaming for chat, agent reasoning,
    and event-driven updates with per-session channel management.

    Usage:
        ws = WebSocketGateway()
        await ws.initialize()
        conn = await ws.accept_connection(user_id="user_1")
        await ws.send(conn.connection_id, WSMessage(msg_type=WSMessageType.CHAT_STREAM, data="Hello"))
    """

    def __init__(self, max_connections: int = 10000, ping_interval_sec: float = 30.0) -> None:
        self._max_connections = max_connections
        self._ping_interval_sec = ping_interval_sec
        self._connections: Dict[str, WSConnection] = {}
        self._message_queues: Dict[str, asyncio.Queue] = {}
        self._event_handlers: Dict[WSMessageType, List[Callable]] = {}
        self._total_messages: int = 0
        self._initialized: bool = False
        self._ping_task: Optional[asyncio.Task] = None
        logger.info("WebSocketGateway created (max_connections=%d)", max_connections)

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._ping_task = asyncio.create_task(self._ping_loop())
        logger.info("WebSocketGateway initialized")

    async def shutdown(self) -> None:
        if self._ping_task:
            self._ping_task.cancel()
            try:
                await self._ping_task
            except asyncio.CancelledError:
                pass
        # Disconnect all clients
        for conn_id in list(self._connections.keys()):
            await self.disconnect(conn_id)
        self._connections.clear()
        self._message_queues.clear()
        self._event_handlers.clear()
        self._initialized = False
        logger.info("WebSocketGateway shutdown complete")

    async def accept_connection(self, user_id: str = "", session_id: str = "") -> Optional[WSConnection]:
        """Accept a new WebSocket connection."""
        if len(self._connections) >= self._max_connections:
            logger.warning("WebSocketGateway: at max connections (%d)", self._max_connections)
            return None

        conn = WSConnection(user_id=user_id, session_id=session_id)
        self._connections[conn.connection_id] = conn
        self._message_queues[conn.connection_id] = asyncio.Queue()
        logger.info("WebSocketGateway: connection %s accepted (user=%s)", conn.connection_id, user_id)
        return conn

    async def disconnect(self, connection_id: str) -> bool:
        """Disconnect a WebSocket client."""
        if connection_id in self._connections:
            del self._connections[connection_id]
        if connection_id in self._message_queues:
            del self._message_queues[connection_id]
        logger.info("WebSocketGateway: disconnected %s", connection_id)
        return True

    async def send(self, connection_id: str, message: WSMessage) -> bool:
        """Send a message to a connected client."""
        if connection_id not in self._message_queues:
            return False
        message.connection_id = connection_id
        await self._message_queues[connection_id].put(message)
        self._total_messages += 1

        if connection_id in self._connections:
            self._connections[connection_id].last_active = time.monotonic()

        return True

    async def broadcast(self, message: WSMessage, channel: Optional[str] = None) -> int:
        """Broadcast a message to all or filtered connections."""
        sent = 0
        for conn_id, conn in self._connections.items():
            if channel is None or channel in conn.channels:
                await self.send(conn_id, message)
                sent += 1
        return sent

    async def subscribe(self, connection_id: str, channel: str) -> bool:
        """Subscribe a connection to a channel."""
        conn = self._connections.get(connection_id)
        if not conn:
            return False
        conn.channels.add(channel)
        return True

    async def unsubscribe(self, connection_id: str, channel: str) -> bool:
        """Unsubscribe a connection from a channel."""
        conn = self._connections.get(connection_id)
        if not conn:
            return False
        conn.channels.discard(channel)
        return True

    def on(self, msg_type: WSMessageType, handler: Callable) -> None:
        """Register an event handler for a message type."""
        self._event_handlers.setdefault(msg_type, []).append(handler)

    async def _handle_message(self, message: WSMessage) -> None:
        """Dispatch a message to registered handlers."""
        handlers = self._event_handlers.get(message.msg_type, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(message)
                else:
                    handler(message)
            except Exception as e:
                logger.error("WebSocketGateway handler error for %s: %s", message.msg_type.value, e)

    async def _ping_loop(self) -> None:
        """Background task to ping clients and clean up stale connections."""
        while True:
            try:
                await asyncio.sleep(self._ping_interval_sec)
                now = time.monotonic()
                stale = [
                    conn_id for conn_id, conn in self._connections.items()
                    if now - conn.last_active > self._ping_interval_sec * 3
                ]
                for conn_id in stale:
                    logger.info("WebSocketGateway: cleaning up stale connection %s", conn_id)
                    await self.disconnect(conn_id)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("WebSocketGateway ping error: %s", e)

    def get_summary(self) -> Dict[str, Any]:
        return {
            "initialized": self._initialized,
            "active_connections": len(self._connections),
            "max_connections": self._max_connections,
            "total_messages": self._total_messages,
            "registered_handlers": {k.value: len(v) for k, v in self._event_handlers.items()},
        }
