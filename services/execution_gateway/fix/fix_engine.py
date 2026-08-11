"""FIX Engine — Financial Information eXchange protocol engine.

Implements the FIX protocol for institutional trading connectivity.
Supports FIX 4.2, 4.4, and 5.0 SP2 with session management,
message parsing, encoding, and sequence number tracking.

FIX Architecture::

    BrokerGateway → FIXEngine → FIXSession → TCP/IP → Counterparty

Supported Versions:
    - FIX 4.2
    - FIX 4.4
    - FIX 5.0 SP2

Usage::

    engine = FIXEngine("FIX.4.4")
    await engine.connect(config)
    await engine.send(new_order_single)
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Optional

from services.execution_gateway.fix.fix_encoder import FIXEncoder
from services.execution_gateway.fix.fix_parser import FIXParser
from services.execution_gateway.fix.fix_session import FIXSession

logger = logging.getLogger(__name__)


class FIXVersion(str, Enum):
    """Supported FIX protocol versions."""

    FIX_4_2 = "FIX.4.2"
    FIX_4_4 = "FIX.4.4"
    FIX_5_0_SP2 = "FIXT.1.1"  # Transport + FIX 5.0 SP2 app messages


class FIXEngine:
    """FIX protocol engine.

    Manages FIX sessions, message encoding/decoding, and protocol
    state. Provides the core FIX connectivity layer.

    Attributes:
        version: FIX protocol version
        sender_comp_id: Sender company ID
        target_comp_id: Target company ID
        parser: FIX message parser
        encoder: FIX message encoder
        _sessions: Active FIX sessions
    """

    def __init__(
        self,
        version: FIXVersion = FIXVersion.FIX_4_4,
        sender_comp_id: str = "",
        target_comp_id: str = "",
    ) -> None:
        self.version = version
        self.sender_comp_id = sender_comp_id
        self.target_comp_id = target_comp_id

        self.parser = FIXParser()
        self.encoder = FIXEncoder(version.value)

        self._sessions: dict[str, FIXSession] = {}

    # ── Session Management ─────────────────────────────────────────

    async def create_session(
        self,
        session_id: str,
        config: Optional[dict[str, Any]] = None,
    ) -> FIXSession:
        """Create a new FIX session.

        Args:
            session_id: Session identifier
            config: Session configuration

        Returns:
            FIXSession instance
        """
        session = FIXSession(
            session_id=session_id,
            sender_comp_id=config.get("sender_comp_id", self.sender_comp_id) if config else self.sender_comp_id,
            target_comp_id=config.get("target_comp_id", self.target_comp_id) if config else self.target_comp_id,
            fix_version=self.version.value,
        )

        self._sessions[session_id] = session
        logger.info("FIX session created: %s", session_id)
        return session

    async def connect_session(
        self,
        session_id: str,
        host: str = "",
        port: int = 0,
    ) -> bool:
        """Connect a FIX session.

        Args:
            session_id: Session identifier
            host: Counterparty host
            port: Counterparty port

        Returns:
            True if connected
        """
        session = self._sessions.get(session_id)
        if not session:
            logger.error("FIX session %s not found", session_id)
            return False

        return await session.connect(host, port)

    async def disconnect_session(self, session_id: str) -> bool:
        """Disconnect a FIX session.

        Args:
            session_id: Session identifier

        Returns:
            True if disconnected
        """
        session = self._sessions.get(session_id)
        if not session:
            return False

        return await session.disconnect()

    # ── Message Operations ─────────────────────────────────────────

    async def send(
        self,
        session_id: str,
        msg_type: str,
        fields: dict[int, str],
    ) -> Optional[str]:
        """Encode and send a FIX message.

        Args:
            session_id: Target session
            msg_type: FIX message type (e.g., 'D' for NewOrderSingle)
            fields: FIX tag → value mapping

        Returns:
            Encoded FIX message string
        """
        session = self._sessions.get(session_id)
        if not session:
            logger.error("Session %s not found", session_id)
            return None

        encoded = self.encoder.encode(msg_type, fields, session.sequence_out)
        await session.send(encoded)
        return encoded

    async def receive(
        self,
        session_id: str,
        raw_message: str,
    ) -> dict[int, str]:
        """Parse a received FIX message.

        Args:
            session_id: Source session
            raw_message: Raw FIX message string

        Returns:
            Parsed FIX tag → value mapping
        """
        session = self._sessions.get(session_id)
        if session:
            await session.receive(raw_message)

        return self.parser.parse(raw_message)

    # ── Common Message Builders ────────────────────────────────────

    def build_logon(
        self,
        username: str = "",
        password: str = "",
        heartbeat_interval: int = 30,
    ) -> dict[int, str]:
        """Build a Logon (A) message.

        Args:
            username: Login username
            password: Login password
            heartbeat_interval: Heartbeat interval in seconds

        Returns:
            FIX tag → value mapping
        """
        return self.encoder.build_logon(
            sender_comp_id=self.sender_comp_id,
            target_comp_id=self.target_comp_id,
            username=username,
            password=password,
            heartbeat_interval=heartbeat_interval,
        )

    def build_logout(self, text: str = "") -> dict[int, str]:
        """Build a Logout (5) message.

        Args:
            text: Reason text

        Returns:
            FIX tag → value mapping
        """
        return self.encoder.build_logout(text)

    def build_new_order_single(
        self,
        cl_ord_id: str,
        symbol: str,
        side: str,
        order_qty: float,
        ord_type: str,
        price: float = 0.0,
        time_in_force: str = "0",  # Day
    ) -> dict[int, str]:
        """Build a NewOrderSingle (D) message.

        Args:
            cl_ord_id: Client order ID (tag 11)
            symbol: Trading symbol (tag 55)
            side: 1=Buy, 2=Sell (tag 54)
            order_qty: Order quantity (tag 38)
            ord_type: 1=Market, 2=Limit (tag 40)
            price: Limit price (tag 44)
            time_in_force: TIF (tag 59)

        Returns:
            FIX tag → value mapping
        """
        return self.encoder.build_new_order_single(
            cl_ord_id=cl_ord_id,
            symbol=symbol,
            side=side,
            order_qty=order_qty,
            ord_type=ord_type,
            price=price,
            time_in_force=time_in_force,
        )

    def build_order_cancel_request(
        self,
        orig_cl_ord_id: str,
        cl_ord_id: str,
        symbol: str,
        side: str,
    ) -> dict[int, str]:
        """Build an OrderCancelRequest (F) message.

        Args:
            orig_cl_ord_id: Original client order ID
            cl_ord_id: Cancel request client order ID
            symbol: Trading symbol
            side: Order side

        Returns:
            FIX tag → value mapping
        """
        return self.encoder.build_order_cancel_request(
            orig_cl_ord_id=orig_cl_ord_id,
            cl_ord_id=cl_ord_id,
            symbol=symbol,
            side=side,
        )

    def build_order_cancel_replace_request(
        self,
        orig_cl_ord_id: str,
        cl_ord_id: str,
        symbol: str,
        side: str,
        order_qty: float,
        ord_type: str,
        price: float = 0.0,
    ) -> dict[int, str]:
        """Build an OrderCancelReplaceRequest (G) message.

        Args:
            orig_cl_ord_id: Original client order ID
            cl_ord_id: New client order ID
            symbol: Trading symbol
            side: Order side
            order_qty: New quantity
            ord_type: Order type
            price: New price

        Returns:
            FIX tag → value mapping
        """
        return self.encoder.build_order_cancel_replace_request(
            orig_cl_ord_id=orig_cl_ord_id,
            cl_ord_id=cl_ord_id,
            symbol=symbol,
            side=side,
            order_qty=order_qty,
            ord_type=ord_type,
            price=price,
        )

    # ── Heartbeat ──────────────────────────────────────────────────

    def build_heartbeat(self, test_req_id: str = "") -> dict[int, str]:
        """Build a Heartbeat (0) message.

        Args:
            test_req_id: Test request ID to echo

        Returns:
            FIX tag → value mapping
        """
        return self.encoder.build_heartbeat(test_req_id)

    def build_test_request(self, test_req_id: str) -> dict[int, str]:
        """Build a TestRequest (1) message.

        Args:
            test_req_id: Test request identifier

        Returns:
            FIX tag → value mapping
        """
        return self.encoder.build_test_request(test_req_id)

    def build_resend_request(
        self,
        begin_seq_no: int,
        end_seq_no: int,
    ) -> dict[int, str]:
        """Build a ResendRequest (2) message.

        Args:
            begin_seq_no: Beginning sequence number
            end_seq_no: Ending sequence number (0 = infinity)

        Returns:
            FIX tag → value mapping
        """
        return self.encoder.build_resend_request(begin_seq_no, end_seq_no)

    def build_reject(
        self,
        ref_seq_num: int,
        ref_msg_type: str = "",
        text: str = "",
    ) -> dict[int, str]:
        """Build a Reject (3) message.

        Args:
            ref_seq_num: Referenced sequence number
            ref_msg_type: Referenced message type
            text: Reject reason

        Returns:
            FIX tag → value mapping
        """
        return self.encoder.build_reject(ref_seq_num, ref_msg_type, text)

    def build_sequence_reset(
        self,
        new_seq_no: int,
        gap_fill: bool = False,
    ) -> dict[int, str]:
        """Build a SequenceReset (4) message.

        Args:
            new_seq_no: New sequence number
            gap_fill: Whether this is a gap fill

        Returns:
            FIX tag → value mapping
        """
        return self.encoder.build_sequence_reset(new_seq_no, gap_fill)

    # ── Query ──────────────────────────────────────────────────────

    def get_session(self, session_id: str) -> Optional[FIXSession]:
        """Get a FIX session.

        Args:
            session_id: Session identifier

        Returns:
            FIXSession or None
        """
        return self._sessions.get(session_id)

    def get_active_sessions(self) -> list[FIXSession]:
        """Get all active FIX sessions.

        Returns:
            List of active FIXSession instances
        """
        return [s for s in self._sessions.values() if s.is_active]

    # ── Properties ─────────────────────────────────────────────────

    @property
    def session_count(self) -> int:
        return len(self._sessions)

    @property
    def active_session_count(self) -> int:
        return len(self.get_active_sessions())

    def to_dict(self) -> dict[str, Any]:
        """Serialize engine state."""
        return {
            "version": self.version.value,
            "sender_comp_id": self.sender_comp_id,
            "target_comp_id": self.target_comp_id,
            "session_count": self.session_count,
            "active_session_count": self.active_session_count,
            "sessions": {sid: s.to_dict() for sid, s in self._sessions.items()},
        }
