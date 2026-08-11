"""
ICYQuant AI Research WebSocket API.

Provides real-time WebSocket endpoints for live research streaming,
collaborative editing notifications, and progress updates.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class WSMessageType(str, Enum):
    # Client → Server
    SUBMIT_RESEARCH = "submit_research"
    SUBSCRIBE_SESSION = "subscribe_session"
    UNSUBSCRIBE_SESSION = "unsubscribe_session"
    SEND_COMMENT = "send_comment"
    PING = "ping"

    # Server → Client
    RESEARCH_PROGRESS = "research_progress"
    RESEARCH_COMPLETED = "research_completed"
    RESEARCH_ERROR = "research_error"
    COMMENT_ADDED = "comment_added"
    SESSION_UPDATED = "session_updated"
    PONG = "pong"
    ERROR = "error"


@dataclass
class WSMessage:
    """A WebSocket message."""
    type: WSMessageType
    payload: dict[str, Any] = field(default_factory=dict)
    request_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_json(self) -> str:
        return json.dumps({
            "type": self.type.value,
            "payload": self.payload,
            "request_id": self.request_id,
            "timestamp": self.timestamp,
        })

    @classmethod
    def from_json(cls, data: str) -> WSMessage:
        obj = json.loads(data)
        return cls(
            type=WSMessageType(obj["type"]),
            payload=obj.get("payload", {}),
            request_id=obj.get("request_id", ""),
            timestamp=obj.get("timestamp", ""),
        )


@dataclass
class WSConfig:
    host: str = "0.0.0.0"
    port: int = 8102
    path: str = "/ws/research"
    heartbeat_interval_seconds: int = 30
    max_connections: int = 1000
    metadata: dict[str, Any] = field(default_factory=dict)


class ResearchWebSocketAPI:
    """WebSocket API for real-time research collaboration.

    Features:
        - Real-time research progress streaming
        - Session subscription for live updates
        - Collaborative comment notifications
        - Heartbeat/ping-pong for connection health
    """

    def __init__(self, platform: Any = None, config: Optional[WSConfig] = None) -> None:
        self._platform = platform
        self._config = config or WSConfig()
        self._connections: dict[str, Any] = {}  # connection_id → connection
        self._subscriptions: dict[str, set[str]] = {}  # session_id → {connection_ids}
        self._message_count = 0

    async def handle_message(self, connection_id: str, raw_message: str) -> Optional[WSMessage]:
        """Handle an incoming WebSocket message."""
        self._message_count += 1

        try:
            msg = WSMessage.from_json(raw_message)
        except (json.JSONDecodeError, KeyError) as exc:
            return WSMessage(type=WSMessageType.ERROR, payload={"error": str(exc)})

        if msg.type == WSMessageType.PING:
            return WSMessage(type=WSMessageType.PONG, request_id=msg.request_id)

        elif msg.type == WSMessageType.SUBMIT_RESEARCH:
            return await self._handle_submit_research(msg)

        elif msg.type == WSMessageType.SUBSCRIBE_SESSION:
            self._subscribe(connection_id, msg.payload.get("session_id", ""))
            return WSMessage(type=WSMessageType.SESSION_UPDATED, payload={"subscribed": True})

        elif msg.type == WSMessageType.UNSUBSCRIBE_SESSION:
            self._unsubscribe(connection_id, msg.payload.get("session_id", ""))
            return WSMessage(type=WSMessageType.SESSION_UPDATED, payload={"unsubscribed": True})

        elif msg.type == WSMessageType.SEND_COMMENT:
            return await self._handle_comment(msg)

        return None

    async def _handle_submit_research(self, msg: WSMessage) -> WSMessage:
        """Handle research submission and stream progress."""
        if self._platform is None:
            return WSMessage(type=WSMessageType.ERROR, payload={"error": "Platform not available"})

        try:
            # Send progress update
            await self._broadcast_progress(msg.request_id, "planning", "Planning research tasks")

            result = await self._platform.submit_research(
                question=msg.payload.get("question", ""),
                context=msg.payload.get("context", {}),
                session_id=msg.payload.get("session_id"),
                user_id=msg.payload.get("user_id"),
            )

            return WSMessage(
                type=WSMessageType.RESEARCH_COMPLETED,
                payload=result,
                request_id=msg.request_id,
            )
        except Exception as exc:
            return WSMessage(
                type=WSMessageType.RESEARCH_ERROR,
                payload={"error": str(exc)},
                request_id=msg.request_id,
            )

    async def _handle_comment(self, msg: WSMessage) -> WSMessage:
        """Handle a new comment and broadcast to subscribers."""
        # Broadcast to all subscribers of the target session
        session_id = msg.payload.get("session_id", "")
        if session_id in self._subscriptions:
            for conn_id in self._subscriptions[session_id]:
                if conn_id in self._connections:
                    await self._send_to(conn_id, WSMessage(
                        type=WSMessageType.COMMENT_ADDED,
                        payload=msg.payload,
                    ))

        return WSMessage(type=WSMessageType.COMMENT_ADDED, payload=msg.payload)

    async def _broadcast_progress(self, request_id: str, phase: str, message: str) -> None:
        """Broadcast research progress to relevant connections."""
        progress_msg = WSMessage(
            type=WSMessageType.RESEARCH_PROGRESS,
            payload={"phase": phase, "message": message},
            request_id=request_id,
        )
        # In production, broadcast to connections subscribed to the session
        for conn_id in self._connections:
            await self._send_to(conn_id, progress_msg)

    def _subscribe(self, connection_id: str, session_id: str) -> None:
        """Subscribe a connection to a session's updates."""
        if session_id not in self._subscriptions:
            self._subscriptions[session_id] = set()
        self._subscriptions[session_id].add(connection_id)

    def _unsubscribe(self, connection_id: str, session_id: str) -> None:
        """Unsubscribe a connection from a session."""
        if session_id in self._subscriptions:
            self._subscriptions[session_id].discard(connection_id)

    async def _send_to(self, connection_id: str, message: WSMessage) -> None:
        """Send a message to a specific connection."""
        # In production, this would use the actual WebSocket connection
        pass

    def register_connection(self, connection_id: str, connection: Any) -> None:
        """Register a new WebSocket connection."""
        self._connections[connection_id] = connection

    def unregister_connection(self, connection_id: str) -> None:
        """Unregister a WebSocket connection."""
        self._connections.pop(connection_id, None)
        for subs in self._subscriptions.values():
            subs.discard(connection_id)

    @property
    def connection_count(self) -> int:
        return len(self._connections)

    @property
    def message_count(self) -> int:
        return self._message_count
