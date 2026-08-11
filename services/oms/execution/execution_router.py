"""ExecutionRouter — routes execution events to appropriate handlers."""
from __future__ import annotations

from typing import Dict, Optional

from .execution_response import ExecutionAck, CancelAck
from .execution_report import ExecutionReport
from .execution_ack_handler import ExecutionAckHandler
from .execution_report_handler import ExecutionReportHandler
from .execution_status import ExecutionStatus


class ExecutionRouter:
    """Routes execution events to the appropriate handler.

    The router is the central dispatcher that receives ACKs and
    reports from the gateway and delegates to the correct handler.
    """

    def __init__(self) -> None:
        self.ack_handler = ExecutionAckHandler()
        self.report_handler = ExecutionReportHandler()

    def route_ack(self, ack: ExecutionAck) -> Dict:
        """Route an ACK to the ACK handler."""
        return self.ack_handler.handle(ack)

    def route_cancel_ack(self, ack: CancelAck) -> Dict:
        """Route a cancel ACK."""
        return {
            "status": "PROCESSED",
            "ack": ack,
            "action": "CONFIRM_CANCEL" if ack.status == ExecutionStatus.CANCELLED else "NONE",
        }

    def route_report(self, report: ExecutionReport,
                     remaining_quantity: float = 0,
                     original_quantity: float = 0,
                     filled_quantity: float = 0) -> Dict:
        """Route an execution report to the report handler."""
        return self.report_handler.handle(
            report,
            remaining_quantity=remaining_quantity,
            original_quantity=original_quantity,
            filled_quantity=filled_quantity,
        )

    # ── Event → OMS Event mapping ──────────────────

    @staticmethod
    def map_to_order_event_type(status: ExecutionStatus) -> Optional[str]:
        """Map execution status to OMS event type name."""
        _mapping = {
            ExecutionStatus.ACCEPTED: "ORDER_WORKING",
            ExecutionStatus.PARTIALLY_FILLED: "ORDER_PARTIAL_FILL",
            ExecutionStatus.FILLED: "ORDER_FILLED",
            ExecutionStatus.REJECTED: "ORDER_REJECTED",
            ExecutionStatus.CANCELLED: "ORDER_CANCELLED",
            ExecutionStatus.EXPIRED: "ORDER_EXPIRED",
        }
        return _mapping.get(status)
