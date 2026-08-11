"""Broker Session — Session management for broker connections.

Manages the lifecycle of a broker connection session including
authentication, heartbeats, reconnection, and session state.

Session Lifecycle::

    Created → Connecting → Authenticated → Active → Terminating → Closed

Usage::

    session = BrokerSession("PRIMARY", credentials)
    await session.start()
    await session.send(request)
    await session.stop()
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class SessionState(str, Enum):
    """Broker session state."""

    CREATED = "CREATED"
    CONNECTING = "CONNECTING"
    AUTHENTICATED = "AUTHENTICATED"
    ACTIVE = "ACTIVE"
    RECONNECTING = "RECONNECTING"
    TERMINATING = "TERMINATING"
    CLOSED = "CLOSED"
    ERROR = "ERROR"


class BrokerSession:
    """Broker connection session manager.

    Handles session lifecycle including authentication, heartbeat
    monitoring, and graceful reconnection.

    Attributes:
        broker_name: Broker identifier
        session_id: Unique session identifier
        state: Current session state
        created_at: Session creation time
        last_activity: Last activity timestamp
        _credentials: Authentication credentials
        _heartbeat_interval: Heartbeat interval in seconds
        _heartbeat_task: Background heartbeat task
        _max_reconnect_attempts: Maximum reconnection attempts
        _reconnect_delay: Base reconnection delay
    """

    def __init__(
        self,
        broker_name: str,
        credentials: Optional[dict[str, Any]] = None,
        heartbeat_interval: float = 30.0,
        max_reconnect_attempts: int = 5,
        reconnect_delay: float = 1.0,
    ) -> None:
        self.broker_name = broker_name
        self.session_id = str(uuid.uuid4())
        self.state = SessionState.CREATED
        self.created_at = datetime.now(timezone.utc)
        self.last_activity = time.monotonic()

        self._credentials = credentials or {}
        self._heartbeat_interval = heartbeat_interval
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._max_reconnect_attempts = max_reconnect_attempts
        self._reconnect_delay = reconnect_delay
        self._reconnect_attempts = 0

    # ── Lifecycle ──────────────────────────────────────────────────

    async def start(self) -> bool:
        """Start the broker session.

        Initiates connection, authentication, and heartbeat.

        Returns:
            True if session started successfully
        """
        self.state = SessionState.CONNECTING
        logger.info("Starting session %s for broker %s", self.session_id, self.broker_name)

        try:
            # Simulate connection + authentication
            await asyncio.sleep(0.01)  # Network round-trip
            self.state = SessionState.AUTHENTICATED

            # Authenticate
            await self._authenticate()

            self.state = SessionState.ACTIVE
            self.last_activity = time.monotonic()

            # Start heartbeat
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

            logger.info(
                "Session %s active for broker %s",
                self.session_id,
                self.broker_name,
            )
            return True
        except Exception as e:
            self.state = SessionState.ERROR
            logger.error("Session start failed: %s", e)
            return False

    async def stop(self) -> bool:
        """Stop the broker session gracefully.

        Returns:
            True if stopped cleanly
        """
        self.state = SessionState.TERMINATING
        logger.info("Stopping session %s", self.session_id)

        # Cancel heartbeat
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        self.state = SessionState.CLOSED
        logger.info("Session %s closed", self.session_id)
        return True

    async def reconnect(self) -> bool:
        """Attempt to reconnect the session.

        Returns:
            True if reconnected successfully
        """
        if self._reconnect_attempts >= self._max_reconnect_attempts:
            logger.error(
                "Max reconnect attempts (%d) reached for broker %s",
                self._max_reconnect_attempts,
                self.broker_name,
            )
            self.state = SessionState.ERROR
            return False

        self.state = SessionState.RECONNECTING
        self._reconnect_attempts += 1

        delay = self._reconnect_delay * (2 ** (self._reconnect_attempts - 1))
        logger.info(
            "Reconnecting session %s (attempt %d/%d, delay %.1fs)",
            self.session_id,
            self._reconnect_attempts,
            self._max_reconnect_attempts,
            delay,
        )

        await asyncio.sleep(min(delay, 30.0))

        # Stop old session
        await self.stop()

        # Start new session
        self.session_id = str(uuid.uuid4())
        return await self.start()

    # ── Communication ──────────────────────────────────────────────

    async def send(self, message: dict[str, Any]) -> dict[str, Any]:
        """Send a message through the session.

        Args:
            message: Message to send

        Returns:
            Response dictionary
        """
        if self.state not in (SessionState.ACTIVE, SessionState.AUTHENTICATED):
            return {"status": "ERROR", "message": f"Session not active (state={self.state.value})"}

        self.last_activity = time.monotonic()
        return {"status": "SENT", "session_id": self.session_id}

    async def receive(self, timeout: float = 5.0) -> Optional[dict[str, Any]]:
        """Receive a message from the session.

        Args:
            timeout: Receive timeout in seconds

        Returns:
            Message dictionary or None on timeout
        """
        if self.state != SessionState.ACTIVE:
            return None

        self.last_activity = time.monotonic()
        # In production, this would read from a message queue
        return None

    # ── Heartbeat ──────────────────────────────────────────────────

    async def _heartbeat_loop(self) -> None:
        """Background heartbeat loop."""
        while self.state == SessionState.ACTIVE:
            try:
                await asyncio.sleep(self._heartbeat_interval)
                if self.state == SessionState.ACTIVE:
                    await self._send_heartbeat()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("Heartbeat error: %s", e)

    async def _send_heartbeat(self) -> None:
        """Send a heartbeat message."""
        idle_time = time.monotonic() - self.last_activity

        if idle_time > self._heartbeat_interval * 3:
            logger.warning(
                "Session %s idle for %.1fs, may need reconnect",
                self.session_id,
                idle_time,
            )

        logger.debug("Heartbeat sent for session %s", self.session_id)

    # ── Authentication ─────────────────────────────────────────────

    async def _authenticate(self) -> bool:
        """Authenticate the session.

        Returns:
            True if authenticated
        """
        api_key = self._credentials.get("api_key", "")
        if not api_key:
            logger.warning("No API key provided for broker %s", self.broker_name)

        logger.debug("Session %s authenticated for %s", self.session_id, self.broker_name)
        return True

    # ── Properties ─────────────────────────────────────────────────

    @property
    def is_active(self) -> bool:
        """Whether the session is active."""
        return self.state == SessionState.ACTIVE

    @property
    def uptime_seconds(self) -> float:
        """Session uptime in seconds."""
        if self.state != SessionState.ACTIVE:
            return 0.0
        return (datetime.now(timezone.utc) - self.created_at).total_seconds()

    @property
    def idle_seconds(self) -> float:
        """Seconds since last activity."""
        return time.monotonic() - self.last_activity

    def to_dict(self) -> dict[str, Any]:
        """Serialize session state."""
        return {
            "broker_name": self.broker_name,
            "session_id": self.session_id,
            "state": self.state.value,
            "created_at": self.created_at.isoformat(),
            "uptime_seconds": self.uptime_seconds,
            "idle_seconds": self.idle_seconds,
            "reconnect_attempts": self._reconnect_attempts,
            "is_active": self.is_active,
        }
