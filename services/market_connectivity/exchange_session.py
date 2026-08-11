"""
Exchange Session — Represents a single connection session to an exchange
with full lifecycle state management and metadata tracking.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class SessionState(str, Enum):
    """Session lifecycle states."""
    CREATED = "created"
    AUTHENTICATING = "authenticating"
    HANDSHAKING = "handshaking"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    CLOSING = "closing"
    DISCONNECTED = "disconnected"
    CLOSED = "closed"
    ERROR = "error"


class SessionType(str, Enum):
    """Types of exchange sessions."""
    MARKET_DATA = "market_data"
    TRADING = "trading"
    ACCOUNT = "account"
    ORDER_MANAGEMENT = "order_management"
    REFERENCE_DATA = "reference_data"
    ANALYTICS = "analytics"


@dataclass
class ExchangeSession:
    """
    Represents a single connection session to an exchange.

    Lifecycle:
        CREATED → AUTHENTICATING → HANDSHAKING → CONNECTED
        CONNECTED → RECONNECTING → HANDSHAKING → CONNECTED
        CONNECTED → CLOSING → DISCONNECTED/CLOSED

    Usage::

        session = ExchangeSession(
            session_id="binance_market_data_001",
            exchange_id="binance",
            session_type=SessionType.MARKET_DATA,
        )
    """

    session_id: str
    exchange_id: str
    session_type: SessionType = SessionType.MARKET_DATA
    state: SessionState = SessionState.CREATED
    credentials: dict[str, Any] = field(default_factory=dict)
    protocol: str = "websocket"
    endpoint: str = ""
    authenticated: bool = False
    handshake_complete: bool = False

    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    connected_at: Optional[datetime] = None
    disconnected_at: Optional[datetime] = None
    last_heartbeat: Optional[datetime] = None
    last_activity: Optional[datetime] = None

    # Metrics
    messages_sent: int = 0
    messages_received: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0
    errors: int = 0
    reconnects: int = 0

    # Metadata
    tags: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_connected(self) -> bool:
        return self.state == SessionState.CONNECTED

    @property
    def is_active(self) -> bool:
        return self.state in (
            SessionState.CREATED,
            SessionState.AUTHENTICATING,
            SessionState.HANDSHAKING,
            SessionState.CONNECTED,
            SessionState.RECONNECTING,
        )

    @property
    def uptime_seconds(self) -> float:
        if self.connected_at is None:
            return 0.0
        return (datetime.now(timezone.utc) - self.connected_at).total_seconds()

    def record_activity(self) -> None:
        """Update the last activity timestamp."""
        self.last_activity = datetime.now(timezone.utc)

    def record_message_sent(self, size: int = 0) -> None:
        """Record an outgoing message."""
        self.messages_sent += 1
        self.bytes_sent += size
        self.record_activity()

    def record_message_received(self, size: int = 0) -> None:
        """Record an incoming message."""
        self.messages_received += 1
        self.bytes_received += size
        self.record_activity()

    def record_error(self) -> None:
        """Record an error occurrence."""
        self.errors += 1
        self.record_activity()

    def record_reconnect(self) -> None:
        """Record a reconnection event."""
        self.reconnects += 1

    def to_dict(self) -> dict[str, Any]:
        """Serialize session to dict."""
        return {
            "session_id": self.session_id,
            "exchange_id": self.exchange_id,
            "session_type": self.session_type.value,
            "state": self.state.value,
            "protocol": self.protocol,
            "endpoint": self.endpoint,
            "authenticated": self.authenticated,
            "created_at": self.created_at.isoformat(),
            "connected_at": self.connected_at.isoformat() if self.connected_at else None,
            "disconnected_at": self.disconnected_at.isoformat() if self.disconnected_at else None,
            "uptime_seconds": self.uptime_seconds,
            "messages_sent": self.messages_sent,
            "messages_received": self.messages_received,
            "errors": self.errors,
            "reconnects": self.reconnects,
            "tags": self.tags,
        }
