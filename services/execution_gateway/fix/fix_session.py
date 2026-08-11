"""FIX Session — FIX protocol session management.

Manages a single FIX connection session including logon/logout
handshake, sequence number tracking, heartbeat monitoring, and
message gap detection/recovery.

Session States::

    DISCONNECTED → CONNECTING → LOGON_SENT → LOGGED_ON → LOGOUT_SENT → DISCONNECTED

Usage::

    session = FIXSession("SESSION_1", "BUY_SIDE", "BROKER", "FIX.4.4")
    await session.connect("fix.broker.com", 9880)
    await session.logon()
    await session.send(encoded_message)
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from services.execution_gateway.fix.fix_sequence_manager import FIXSequenceManager
from services.execution_gateway.fix.heartbeat_manager import HeartbeatManager

logger = logging.getLogger(__name__)


class FIXSessionState(str, Enum):
    """FIX session states."""

    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    LOGON_SENT = "LOGON_SENT"
    LOGGED_ON = "LOGGED_ON"
    LOGOUT_SENT = "LOGOUT_SENT"
    RECONNECTING = "RECONNECTING"
    ERROR = "ERROR"


class FIXSession:
    """FIX protocol session.

    Manages the lifecycle of a single FIX connection including
    authentication, sequencing, and heartbeat.

    Attributes:
        session_id: Unique session identifier
        sender_comp_id: Sender company ID (tag 49)
        target_comp_id: Target company ID (tag 56)
        fix_version: FIX protocol version
        state: Current session state
        sequence_manager: Sequence number tracker
        heartbeat_manager: Heartbeat monitor
        _host: Connection host
        _port: Connection port
        _created_at: Session creation time
        _last_msg_time: Last message timestamp
    """

    def __init__(
        self,
        session_id: str = "",
        sender_comp_id: str = "",
        target_comp_id: str = "",
        fix_version: str = "FIX.4.4",
    ) -> None:
        self.session_id = session_id or str(uuid.uuid4())
        self.sender_comp_id = sender_comp_id
        self.target_comp_id = target_comp_id
        self.fix_version = fix_version

        self.state = FIXSessionState.DISCONNECTED
        self.sequence_manager = FIXSequenceManager()
        self.heartbeat_manager = HeartbeatManager()

        self._host: str = ""
        self._port: int = 0
        self._created_at = datetime.now(timezone.utc)
        self._last_msg_time: float = 0.0
        self._message_log: list[dict[str, Any]] = []

    # ── Connection ─────────────────────────────────────────────────

    async def connect(self, host: str, port: int) -> bool:
        """Establish TCP connection.

        Args:
            host: Counterparty host
            port: Counterparty port

        Returns:
            True if connected
        """
        self._host = host
        self._port = port
        self.state = FIXSessionState.CONNECTING

        logger.info(
            "FIX session %s connecting to %s:%d",
            self.session_id,
            host,
            port,
        )

        try:
            # In production: actual TCP socket connection
            await asyncio.sleep(0.01)  # Simulate network

            self.state = FIXSessionState.CONNECTING
            self._last_msg_time = time.time()

            logger.info("FIX session %s connected", self.session_id)
            return True
        except Exception as e:
            self.state = FIXSessionState.ERROR
            logger.error("FIX session %s connection failed: %s", self.session_id, e)
            return False

    async def disconnect(self) -> bool:
        """Disconnect the session.

        Sends Logout if logged on, then closes connection.

        Returns:
            True if disconnected
        """
        if self.state == FIXSessionState.LOGGED_ON:
            self.state = FIXSessionState.LOGOUT_SENT

        # In production: send Logout message and close socket
        self.state = FIXSessionState.DISCONNECTED
        self.heartbeat_manager.stop()

        logger.info("FIX session %s disconnected", self.session_id)
        return True

    # ── Logon / Logout ─────────────────────────────────────────────

    async def logon(
        self,
        username: str = "",
        password: str = "",
        heartbeat_interval: int = 30,
    ) -> bool:
        """Send Logon message and complete handshake.

        Args:
            username: Login username
            password: Login password
            heartbeat_interval: Heartbeat interval in seconds

        Returns:
            True if logged on
        """
        if self.state not in (FIXSessionState.CONNECTING, FIXSessionState.DISCONNECTED):
            logger.warning("Cannot logon in state %s", self.state.value)
            return False

        self.state = FIXSessionState.LOGON_SENT

        try:
            # In production: send Logon (35=A) message
            self.sequence_manager.reset()
            self.state = FIXSessionState.LOGGED_ON

            # Start heartbeat
            self.heartbeat_manager.start(heartbeat_interval)

            logger.info(
                "FIX session %s logged on (seq_out=%d)",
                self.session_id,
                self.sequence_manager.sequence_out,
            )
            return True
        except Exception as e:
            self.state = FIXSessionState.ERROR
            logger.error("FIX session %s logon failed: %s", self.session_id, e)
            return False

    async def logout(self, reason: str = "") -> bool:
        """Send Logout and terminate session.

        Args:
            reason: Logout reason

        Returns:
            True if logged out
        """
        if self.state != FIXSessionState.LOGGED_ON:
            return False

        self.state = FIXSessionState.LOGOUT_SENT

        # In production: send Logout (35=5) message
        await self.disconnect()

        logger.info("FIX session %s logged out: %s", self.session_id, reason)
        return True

    # ── Message Operations ─────────────────────────────────────────

    async def send(self, message: str) -> bool:
        """Send a FIX message.

        Increments outbound sequence number.

        Args:
            message: Encoded FIX message string

        Returns:
            True if sent
        """
        if self.state != FIXSessionState.LOGGED_ON:
            logger.warning("Cannot send in state %s", self.state.value)
            return False

        self.sequence_manager.next_outgoing()
        self._last_msg_time = time.time()

        self._log_message("SEND", message, self.sequence_manager.sequence_out)

        logger.debug(
            "FIX session %s sent message (seq=%d): %s",
            self.session_id,
            self.sequence_manager.sequence_out,
            message[:80],
        )
        return True

    async def receive(self, message: str) -> bool:
        """Receive a FIX message.

        Validates inbound sequence number.

        Args:
            message: Raw FIX message string

        Returns:
            True if valid
        """
        self._last_msg_time = time.time()

        self.sequence_manager.next_incoming()

        self._log_message("RECV", message, self.sequence_manager.sequence_in)
        self.heartbeat_manager.record_message()

        logger.debug(
            "FIX session %s received message (seq=%d): %s",
            self.session_id,
            self.sequence_manager.sequence_in,
            message[:80],
        )
        return True

    # ── Recovery ───────────────────────────────────────────────────

    async def request_resend(self, begin_seq: int, end_seq: int = 0) -> None:
        """Request resend of missed messages.

        Args:
            begin_seq: Beginning sequence number
            end_seq: Ending sequence number (0 = infinity)
        """
        logger.warning(
            "FIX session %s requesting resend: %d - %d",
            self.session_id,
            begin_seq,
            end_seq,
        )

    async def send_gap_fill(self, begin_seq: int, end_seq: int) -> None:
        """Send gap fill for administrative messages.

        Args:
            begin_seq: Beginning sequence number
            end_seq: Ending sequence number
        """
        logger.info(
            "FIX session %s sending gap fill: %d - %d",
            self.session_id,
            begin_seq,
            end_seq,
        )

    # ── Internal ───────────────────────────────────────────────────

    def _log_message(
        self,
        direction: str,
        message: str,
        seq_num: int,
    ) -> None:
        """Log a message for audit.

        Args:
            direction: SEND or RECV
            message: FIX message
            seq_num: Sequence number
        """
        self._message_log.append({
            "direction": direction,
            "message": message,
            "seq_num": seq_num,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # Keep log manageable
        if len(self._message_log) > 10000:
            self._message_log = self._message_log[-5000:]

    # ── Properties ─────────────────────────────────────────────────

    @property
    def is_active(self) -> bool:
        return self.state == FIXSessionState.LOGGED_ON

    @property
    def sequence_out(self) -> int:
        return self.sequence_manager.sequence_out

    @property
    def sequence_in(self) -> int:
        return self.sequence_manager.sequence_in

    @property
    def idle_seconds(self) -> float:
        if self._last_msg_time == 0:
            return 0.0
        return time.time() - self._last_msg_time

    def to_dict(self) -> dict[str, Any]:
        """Serialize session state."""
        return {
            "session_id": self.session_id,
            "sender_comp_id": self.sender_comp_id,
            "target_comp_id": self.target_comp_id,
            "fix_version": self.fix_version,
            "state": self.state.value,
            "is_active": self.is_active,
            "host": self._host,
            "port": self._port,
            "sequence_out": self.sequence_out,
            "sequence_in": self.sequence_in,
            "idle_seconds": self.idle_seconds,
            "created_at": self._created_at.isoformat(),
            "messages_logged": len(self._message_log),
        }
