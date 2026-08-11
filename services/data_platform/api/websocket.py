"""
ICYQuant Data Platform WebSocket API.

Real-time WebSocket endpoints for live market data streaming, event
notifications, and bidirectional communication.
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
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    QUERY = "query"
    PING = "ping"

    # Server → Client
    DATA_UPDATE = "data_update"
    TRADE = "trade"
    QUOTE = "quote"
    ORDERBOOK = "orderbook"
    ERROR = "error"
    PONG = "pong"
    SUBSCRIPTION_CONFIRMED = "subscription_confirmed"


@dataclass
class WSMessage:
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
        )


@dataclass
class WSConfig:
    host: str = "0.0.0.0"
    port: int = 8202
    path: str = "/ws/data"
    heartbeat_interval_seconds: int = 30
    max_connections: int = 5000
    metadata: dict[str, Any] = field(default_factory=dict)


class DataPlatformWebSocket:
    """WebSocket API for real-time data streaming.

    Features:
        - Real-time market data streaming (trades, quotes, order books)
        - Subscription management per connection
        - Bidirectional communication
        - Heartbeat/ping-pong
        - Connection lifecycle management
    """

    def __init__(self, platform: Any = None, config: Optional[WSConfig] = None) -> None:
        self._platform = platform
        self._config = config or WSConfig()
        self._connections: dict[str, Any] = {}
        self._subscriptions: dict[str, set[str]] = {}  # instrument → {conn_ids}
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

        elif msg.type == WSMessageType.SUBSCRIBE:
            instruments = msg.payload.get("instruments", [])
            for instr in instruments:
                if instr not in self._subscriptions:
                    self._subscriptions[instr] = set()
                self._subscriptions[instr].add(connection_id)
            return WSMessage(
                type=WSMessageType.SUBSCRIPTION_CONFIRMED,
                payload={"instruments": instruments},
                request_id=msg.request_id,
            )

        elif msg.type == WSMessageType.UNSUBSCRIBE:
            instruments = msg.payload.get("instruments", [])
            for instr in instruments:
                if instr in self._subscriptions:
                    self._subscriptions[instr].discard(connection_id)
            return WSMessage(
                type=WSMessageType.SUBSCRIPTION_CONFIRMED,
                payload={"action": "unsubscribed", "instruments": instruments},
            )

        return None

    async def broadcast(self, instrument: str, data: dict[str, Any], msg_type: WSMessageType) -> None:
        """Broadcast data to all connections subscribed to an instrument."""
        if instrument in self._subscriptions:
            msg = WSMessage(type=msg_type, payload=data)
            for conn_id in self._subscriptions[instrument]:
                await self._send_to(conn_id, msg)

    async def _send_to(self, connection_id: str, message: WSMessage) -> None:
        """Send a message to a specific connection."""
        # In production, sends over actual WebSocket connection
        pass

    def register_connection(self, connection_id: str, connection: Any) -> None:
        self._connections[connection_id] = connection

    def unregister_connection(self, connection_id: str) -> None:
        self._connections.pop(connection_id, None)
        for subs in self._subscriptions.values():
            subs.discard(connection_id)

    @property
    def connection_count(self) -> int:
        return len(self._connections)

    @property
    def message_count(self) -> int:
        return self._message_count
