"""FIX Parser — FIX message parser for inbound messages.

Parses raw FIX message strings into tag-value dictionaries.
Supports standard FIX delimiter (SOH) parsing with validation.

FIX Message Structure::

    "8=FIX.4.4\x019=123\x0135=D\x0149=SENDER\x01..."

Usage::

    parser = FIXParser()
    fields = parser.parse(raw_fix_message)
    msg_type = parser.get_message_type(fields)
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# FIX message type constants
FIX_MSG_TYPES: dict[str, str] = {
    "0": "Heartbeat",
    "1": "TestRequest",
    "2": "ResendRequest",
    "3": "Reject",
    "4": "SequenceReset",
    "5": "Logout",
    "8": "ExecutionReport",
    "9": "OrderCancelReject",
    "A": "Logon",
    "D": "NewOrderSingle",
    "F": "OrderCancelRequest",
    "G": "OrderCancelReplaceRequest",
    "j": "BusinessMessageReject",
}

# FIX side values
FIX_SIDES: dict[str, str] = {
    "1": "BUY",
    "2": "SELL",
    "5": "SELL_SHORT",
    "6": "SELL_SHORT_EXEMPT",
}

# FIX order type values
FIX_ORD_TYPES: dict[str, str] = {
    "1": "MARKET",
    "2": "LIMIT",
    "3": "STOP",
    "4": "STOP_LIMIT",
}

# FIX order status values
FIX_ORD_STATUS: dict[str, str] = {
    "0": "NEW",
    "1": "PARTIALLY_FILLED",
    "2": "FILLED",
    "4": "CANCELLED",
    "6": "PENDING_CANCEL",
    "8": "REJECTED",
}


class FIXParser:
    """FIX protocol message parser.

    Parses raw FIX message strings into structured tag-value pairs.

    Attributes:
        _delimiter: FIX field delimiter (SOH = \x01)
        _parse_stats: Parser statistics
    """

    def __init__(self) -> None:
        self._delimiter = "\x01"
        self._parse_stats = {
            "messages_parsed": 0,
            "parse_errors": 0,
        }

    # ── Parsing ────────────────────────────────────────────────────

    def parse(self, raw_message: str) -> dict[int, str]:
        """Parse a raw FIX message string.

        Args:
            raw_message: Raw FIX message with SOH delimiters

        Returns:
            Dict of tag (int) → value (str)
        """
        if not raw_message:
            self._parse_stats["parse_errors"] += 1
            return {}

        try:
            fields: dict[int, str] = {}

            # Split by SOH delimiter
            pairs = raw_message.strip(self._delimiter).split(self._delimiter)

            for pair in pairs:
                if "=" not in pair:
                    continue

                tag_str, value = pair.split("=", 1)
                try:
                    tag = int(tag_str)
                    fields[tag] = value
                except ValueError:
                    logger.warning("Invalid FIX tag: %s", tag_str)
                    continue

            self._parse_stats["messages_parsed"] += 1
            return fields

        except Exception as e:
            self._parse_stats["parse_errors"] += 1
            logger.error("FIX parse error: %s", e)
            return {}

    # ── Field Access ───────────────────────────────────────────────

    @staticmethod
    def get_message_type(fields: dict[int, str]) -> str:
        """Get message type (tag 35).

        Args:
            fields: Parsed FIX fields

        Returns:
            Message type string (e.g., 'D', '8')
        """
        return fields.get(35, "")

    @staticmethod
    def get_message_type_name(fields: dict[int, str]) -> str:
        """Get human-readable message type name.

        Args:
            fields: Parsed FIX fields

        Returns:
            Message type name (e.g., 'NewOrderSingle')
        """
        msg_type = fields.get(35, "")
        return FIX_MSG_TYPES.get(msg_type, f"Unknown({msg_type})")

    @staticmethod
    def get_sender_comp_id(fields: dict[int, str]) -> str:
        """Get sender company ID (tag 49).

        Args:
            fields: Parsed FIX fields

        Returns:
            Sender company ID
        """
        return fields.get(49, "")

    @staticmethod
    def get_target_comp_id(fields: dict[int, str]) -> str:
        """Get target company ID (tag 56).

        Args:
            fields: Parsed FIX fields

        Returns:
            Target company ID
        """
        return fields.get(56, "")

    @staticmethod
    def get_seq_num(fields: dict[int, str]) -> int:
        """Get message sequence number (tag 34).

        Args:
            fields: Parsed FIX fields

        Returns:
            Sequence number
        """
        try:
            return int(fields.get(34, "0"))
        except ValueError:
            return 0

    @staticmethod
    def get_order_id(fields: dict[int, str]) -> str:
        """Get order ID (tag 37).

        Args:
            fields: Parsed FIX fields

        Returns:
            Order ID
        """
        return fields.get(37, "")

    @staticmethod
    def get_cl_ord_id(fields: dict[int, str]) -> str:
        """Get client order ID (tag 11).

        Args:
            fields: Parsed FIX fields

        Returns:
            Client order ID
        """
        return fields.get(11, "")

    @staticmethod
    def get_exec_type(fields: dict[int, str]) -> str:
        """Get execution type (tag 150).

        Args:
            fields: Parsed FIX fields

        Returns:
            Execution type value
        """
        return fields.get(150, "")

    @staticmethod
    def get_ord_status(fields: dict[int, str]) -> str:
        """Get order status (tag 39).

        Args:
            fields: Parsed FIX fields

        Returns:
            Order status value
        """
        return FIX_ORD_STATUS.get(fields.get(39, ""), "UNKNOWN")

    # ── Execution Report Parsing ───────────────────────────────────

    @staticmethod
    def parse_execution_report(
        fields: dict[int, str],
    ) -> dict[str, Any]:
        """Parse an ExecutionReport (8) message.

        Args:
            fields: Parsed FIX fields

        Returns:
            Structured execution report
        """
        return {
            "order_id": fields.get(37, ""),
            "cl_ord_id": fields.get(11, ""),
            "exec_id": fields.get(17, ""),
            "exec_type": fields.get(150, ""),
            "ord_status": FIX_ORD_STATUS.get(fields.get(39, ""), "UNKNOWN"),
            "symbol": fields.get(55, ""),
            "side": FIX_SIDES.get(fields.get(54, ""), "UNKNOWN"),
            "order_qty": float(fields.get(38, "0")),
            "last_qty": float(fields.get(32, "0")),
            "last_px": float(fields.get(31, "0")),
            "cum_qty": float(fields.get(14, "0")),
            "avg_px": float(fields.get(6, "0")),
            "leaves_qty": float(fields.get(151, "0")),
            "transact_time": fields.get(60, ""),
            "text": fields.get(58, ""),
        }

    # ── Validation ─────────────────────────────────────────────────

    def validate(self, fields: dict[int, str]) -> tuple[bool, str]:
        """Validate a parsed FIX message.

        Checks for required header fields and message structure.

        Args:
            fields: Parsed FIX fields

        Returns:
            (is_valid, error_message)
        """
        # Required header fields
        required_tags = [8, 9, 35, 49, 56, 34]

        for tag in required_tags:
            if tag not in fields:
                return False, f"Missing required tag {tag}"

        # Check body length (tag 9) if available
        body_length_str = fields.get(9, "0")
        try:
            body_length = int(body_length_str)
            if body_length < 0:
                return False, f"Invalid body length: {body_length}"
        except ValueError:
            return False, f"Non-numeric body length: {body_length_str}"

        return True, ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize parser state."""
        return {
            "messages_parsed": self._parse_stats["messages_parsed"],
            "parse_errors": self._parse_stats["parse_errors"],
        }
