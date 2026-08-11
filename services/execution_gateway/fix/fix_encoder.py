"""FIX Encoder — FIX message encoder for outbound messages.

Encodes tag-value dictionaries into properly formatted FIX message
strings with SOH delimiters and checksum computation.

FIX Message Format::

    "8=FIX.4.4\x019=123\x0135=D\x01...\x0110=128\x01"

Usage::

    encoder = FIXEncoder("FIX.4.4")
    msg = encoder.encode("D", {11: "ORD001", 55: "AAPL", ...})
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

# Standard FIX header tags (in order)
HEADER_TAGS = [8, 9, 35, 49, 56, 34, 52]

# Standard FIX trailer tag
TRAILER_TAG = 10


class FIXEncoder:
    """FIX protocol message encoder.

    Encodes structured FIX fields into wire-format FIX message strings.

    Attributes:
        fix_version: FIX protocol version string
        _delimiter: FIX field delimiter (SOH = \x01)
    """

    def __init__(self, fix_version: str = "FIX.4.4") -> None:
        self.fix_version = fix_version
        self._delimiter = "\x01"

    # ── Core Encoding ──────────────────────────────────────────────

    def encode(
        self,
        msg_type: str,
        fields: dict[int, str],
        seq_num: int = 1,
        sending_time: str = "",
    ) -> str:
        """Encode a complete FIX message.

        Builds header, body, and trailer with correct checksum.

        Args:
            msg_type: FIX message type (e.g., 'D')
            fields: Tag → value mapping
            seq_num: Outgoing sequence number
            sending_time: Sending time (UTC)

        Returns:
            Complete FIX message string
        """
        if not sending_time:
            sending_time = time.strftime("%Y%m%d-%H:%M:%S.000", time.gmtime())

        # Build all fields
        all_fields: dict[int, str] = {}

        # Header
        all_fields[8] = self.fix_version
        all_fields[35] = msg_type
        all_fields[34] = str(seq_num)
        all_fields[52] = sending_time

        # Copy sender/target if present in fields
        for tag in [49, 56]:
            if tag in fields:
                all_fields[tag] = fields[tag]

        # Body (exclude header and trailer tags from fields)
        for tag, value in fields.items():
            if tag not in HEADER_TAGS and tag != TRAILER_TAG:
                all_fields[tag] = str(value)

        # Encode body (everything after tag 8)
        body_parts = []
        for tag, value in all_fields.items():
            if tag == 8:
                continue
            body_parts.append(f"{tag}={value}")

        body_str = self._delimiter.join(body_parts)

        # Body length (tag 9)
        all_fields[9] = str(len(body_str))

        # Build complete message
        message_parts = [f"8={all_fields[8]}", f"9={all_fields[9]}"]
        for tag, value in all_fields.items():
            if tag in (8, 9):
                continue
            message_parts.append(f"{tag}={value}")

        message_str = self._delimiter.join(message_parts)

        # Checksum (tag 10)
        checksum = self._compute_checksum(message_str)
        message_str += f"{self._delimiter}10={checksum:03d}{self._delimiter}"

        return message_str

    # ── Checksum ───────────────────────────────────────────────────

    def _compute_checksum(self, message: str) -> int:
        """Compute FIX checksum (sum of all bytes mod 256).

        Args:
            message: Message string up to (but not including) tag 10

        Returns:
            Checksum value (0-255)
        """
        total = sum(ord(c) for c in message)
        return total % 256

    # ── Message Builders ───────────────────────────────────────────

    def build_logon(
        self,
        sender_comp_id: str,
        target_comp_id: str,
        username: str = "",
        password: str = "",
        heartbeat_interval: int = 30,
        encrypt_method: int = 0,
    ) -> dict[int, str]:
        """Build Logon (A) message fields.

        Args:
            sender_comp_id: Sender company ID
            target_comp_id: Target company ID
            username: Username
            password: Password
            heartbeat_interval: Heartbeat interval (seconds)
            encrypt_method: Encryption method (0=None)

        Returns:
            FIX tag → value mapping
        """
        fields: dict[int, str] = {
            49: sender_comp_id,
            56: target_comp_id,
            98: str(encrypt_method),
            108: str(heartbeat_interval),
        }

        if username:
            fields[553] = username
        if password:
            fields[554] = password

        return fields

    def build_logout(self, text: str = "") -> dict[int, str]:
        """Build Logout (5) message fields.

        Args:
            text: Logout reason

        Returns:
            FIX tag → value mapping
        """
        fields: dict[int, str] = {}
        if text:
            fields[58] = text
        return fields

    def build_heartbeat(self, test_req_id: str = "") -> dict[int, str]:
        """Build Heartbeat (0) message fields.

        Args:
            test_req_id: Test request ID to echo

        Returns:
            FIX tag → value mapping
        """
        fields: dict[int, str] = {}
        if test_req_id:
            fields[112] = test_req_id
        return fields

    def build_test_request(self, test_req_id: str) -> dict[int, str]:
        """Build TestRequest (1) message fields.

        Args:
            test_req_id: Test request identifier

        Returns:
            FIX tag → value mapping
        """
        return {112: test_req_id}

    def build_resend_request(
        self,
        begin_seq_no: int,
        end_seq_no: int = 0,
    ) -> dict[int, str]:
        """Build ResendRequest (2) message fields.

        Args:
            begin_seq_no: Beginning sequence number
            end_seq_no: Ending sequence number (0 = infinity)

        Returns:
            FIX tag → value mapping
        """
        return {
            7: str(begin_seq_no),
            16: str(end_seq_no),
        }

    def build_reject(
        self,
        ref_seq_num: int,
        ref_msg_type: str = "",
        text: str = "",
    ) -> dict[int, str]:
        """Build Reject (3) message fields.

        Args:
            ref_seq_num: Referenced sequence number
            ref_msg_type: Referenced message type
            text: Reject reason text

        Returns:
            FIX tag → value mapping
        """
        fields: dict[int, str] = {
            45: str(ref_seq_num),
        }
        if ref_msg_type:
            fields[372] = ref_msg_type
        if text:
            fields[58] = text
        return fields

    def build_sequence_reset(
        self,
        new_seq_no: int,
        gap_fill: bool = False,
    ) -> dict[int, str]:
        """Build SequenceReset (4) message fields.

        Args:
            new_seq_no: New sequence number
            gap_fill: Whether this is a gap fill

        Returns:
            FIX tag → value mapping
        """
        return {
            36: str(new_seq_no),
            123: "Y" if gap_fill else "N",
        }

    def build_new_order_single(
        self,
        cl_ord_id: str,
        symbol: str,
        side: str,
        order_qty: float,
        ord_type: str,
        price: float = 0.0,
        time_in_force: str = "0",
        account: str = "",
        **kwargs,
    ) -> dict[int, str]:
        """Build NewOrderSingle (D) message fields.

        Args:
            cl_ord_id: Client order ID (tag 11)
            symbol: Trading symbol (tag 55)
            side: Order side (tag 54): 1=Buy, 2=Sell
            order_qty: Order quantity (tag 38)
            ord_type: Order type (tag 40): 1=Market, 2=Limit
            price: Limit price (tag 44)
            time_in_force: TIF (tag 59): 0=Day, 1=GTC, 3=IOC, 4=FOK
            account: Account (tag 1)
            **kwargs: Additional FIX tags

        Returns:
            FIX tag → value mapping
        """
        fields: dict[int, str] = {
            11: cl_ord_id,
            55: symbol,
            54: self._normalize_side(side),
            38: str(order_qty),
            40: self._normalize_ord_type(ord_type),
            59: time_in_force,
        }

        if price > 0:
            fields[44] = str(price)

        if account:
            fields[1] = account

        # Add any additional tags
        for key, value in kwargs.items():
            try:
                tag = int(key)
                fields[tag] = str(value)
            except ValueError:
                pass

        return fields

    def build_order_cancel_request(
        self,
        orig_cl_ord_id: str,
        cl_ord_id: str,
        symbol: str,
        side: str,
    ) -> dict[int, str]:
        """Build OrderCancelRequest (F) message fields.

        Args:
            orig_cl_ord_id: Original client order ID
            cl_ord_id: Cancel request client order ID
            symbol: Trading symbol
            side: Order side

        Returns:
            FIX tag → value mapping
        """
        return {
            41: orig_cl_ord_id,
            11: cl_ord_id,
            55: symbol,
            54: self._normalize_side(side),
        }

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
        """Build OrderCancelReplaceRequest (G) message fields.

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
        fields: dict[int, str] = {
            41: orig_cl_ord_id,
            11: cl_ord_id,
            55: symbol,
            54: self._normalize_side(side),
            38: str(order_qty),
            40: self._normalize_ord_type(ord_type),
        }

        if price > 0:
            fields[44] = str(price)

        return fields

    # ── Normalization ──────────────────────────────────────────────

    @staticmethod
    def _normalize_side(side: str) -> str:
        """Normalize side to FIX value.

        Args:
            side: BUY, SELL, etc.

        Returns:
            FIX side value
        """
        side_map = {
            "BUY": "1",
            "SELL": "2",
            "SELL_SHORT": "5",
        }
        return side_map.get(side.upper(), side)

    @staticmethod
    def _normalize_ord_type(ord_type: str) -> str:
        """Normalize order type to FIX value.

        Args:
            ord_type: MARKET, LIMIT, etc.

        Returns:
            FIX order type value
        """
        type_map = {
            "MARKET": "1",
            "LIMIT": "2",
            "STOP": "3",
            "STOP_LIMIT": "4",
        }
        return type_map.get(ord_type.upper(), ord_type)

    def to_dict(self) -> dict[str, Any]:
        """Serialize encoder state."""
        return {
            "fix_version": self.fix_version,
        }
