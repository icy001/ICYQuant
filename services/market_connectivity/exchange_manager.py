"""
Exchange Manager — Manages the operational lifecycle of individual
exchange connections including connect, disconnect, authenticate,
and session state management.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from .exchange_registry import ExchangeRegistry
from .exchange_session import ExchangeSession, SessionState, SessionType

logger = logging.getLogger(__name__)


class ExchangeManager:
    """
    Per-exchange operational manager.

    Handles the full lifecycle of an exchange connection:
    create session → authenticate → handshake → maintain → disconnect.

    Usage::

        registry = ExchangeRegistry()
        manager = ExchangeManager(registry)
        await manager.initialize()
        session = await manager.create_session("binance", SessionType.TRADING)
        await manager.connect_session(session)
    """

    def __init__(self, registry: ExchangeRegistry) -> None:
        self._registry = registry
        self._sessions: dict[str, dict[str, ExchangeSession]] = {}
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the exchange manager."""
        logger.info("ExchangeManager initialized.")

    # ---- Session Management ----

    async def create_session(
        self,
        exchange_id: str,
        session_type: SessionType = SessionType.MARKET_DATA,
        credentials: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Optional[ExchangeSession]:
        """Create a new exchange session."""
        exchange = await self._registry.get(exchange_id)
        if exchange is None:
            logger.error("Exchange not found: %s", exchange_id)
            return None

        session_id = f"{exchange_id}_{session_type.value}_{datetime.now(timezone.utc).timestamp()}"
        session = ExchangeSession(
            session_id=session_id,
            exchange_id=exchange_id,
            session_type=session_type,
            credentials=credentials or {},
            **kwargs,
        )

        async with self._lock:
            if exchange_id not in self._sessions:
                self._sessions[exchange_id] = {}
            self._sessions[exchange_id][session_id] = session

        logger.info("Session created: %s for %s (%s)", session_id, exchange_id, session_type.value)
        return session

    async def connect_session(self, session: ExchangeSession) -> bool:
        """Connect an existing session (authenticate + handshake)."""
        try:
            session.state = SessionState.AUTHENTICATING
            logger.info("Authenticating session: %s", session.session_id)
            await asyncio.sleep(0.01)  # placeholder for actual auth
            session.authenticated = True

            session.state = SessionState.HANDSHAKING
            logger.info("Handshaking session: %s", session.session_id)
            await asyncio.sleep(0.01)  # placeholder for actual handshake

            session.state = SessionState.CONNECTED
            session.connected_at = datetime.now(timezone.utc)
            logger.info("Session connected: %s", session.session_id)
            return True
        except Exception:
            logger.exception("Failed to connect session: %s", session.session_id)
            session.state = SessionState.ERROR
            return False

    async def disconnect_session(self, session: ExchangeSession) -> bool:
        """Disconnect an active session."""
        if session.state in (SessionState.DISCONNECTED, SessionState.CLOSED):
            return True

        try:
            session.state = SessionState.CLOSING
            logger.info("Disconnecting session: %s", session.session_id)
            await asyncio.sleep(0.01)  # placeholder for actual disconnection
            session.state = SessionState.DISCONNECTED
            session.disconnected_at = datetime.now(timezone.utc)
            logger.info("Session disconnected: %s", session.session_id)
            return True
        except Exception:
            logger.exception("Failed to disconnect session: %s", session.session_id)
            session.state = SessionState.ERROR
            return False

    async def get_sessions(
        self, exchange_id: str, session_type: Optional[SessionType] = None
    ) -> list[ExchangeSession]:
        """Get sessions for an exchange, optionally filtered by type."""
        sessions = self._sessions.get(exchange_id, {})
        if session_type:
            return [s for s in sessions.values() if s.session_type == session_type]
        return list(sessions.values())

    async def get_active_sessions(self, exchange_id: str) -> list[ExchangeSession]:
        """Get all active (connected) sessions for an exchange."""
        sessions = self._sessions.get(exchange_id, {})
        return [
            s for s in sessions.values()
            if s.state == SessionState.CONNECTED
        ]

    async def disconnect_all_sessions(self, exchange_id: str) -> None:
        """Disconnect all sessions for an exchange."""
        sessions = self._sessions.get(exchange_id, {})
        tasks = [self.disconnect_session(s) for s in sessions.values()]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def remove_session(self, exchange_id: str, session_id: str) -> bool:
        """Remove a session from tracking."""
        async with self._lock:
            if exchange_id in self._sessions:
                removed = self._sessions[exchange_id].pop(session_id, None)
                if removed:
                    logger.info("Session removed: %s", session_id)
                    return True
            return False

    async def get_session_count(self, exchange_id: str) -> int:
        """Get total session count for an exchange."""
        return len(self._sessions.get(exchange_id, {}))

    async def get_summary(self) -> dict[str, Any]:
        """Get summary of all managed sessions."""
        total_sessions = sum(len(sessions) for sessions in self._sessions.values())
        active_sessions = sum(
            sum(1 for s in sessions.values() if s.state == SessionState.CONNECTED)
            for sessions in self._sessions.values()
        )
        return {
            "total_exchanges": len(self._sessions),
            "total_sessions": total_sessions,
            "active_sessions": active_sessions,
        }

    async def shutdown(self) -> None:
        """Disconnect all sessions and shut down."""
        for exchange_id in list(self._sessions.keys()):
            await self.disconnect_all_sessions(exchange_id)
        logger.info("ExchangeManager shut down.")
