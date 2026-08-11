"""ExecutionReportHandler — processes execution reports (fills, rejects)."""
from __future__ import annotations

from typing import Dict, List, Optional

from .execution_report import ExecutionReport
from .execution_status import ExecutionStatus
from .execution_error import (
    ExecutionError,
    ExecutionQuantityExceededError,
)


class ExecutionReportHandler:
    """Processes execution reports.

    Flow:
        ExecutionReport
             ↓
        Validate Execution ID
             ↓
        Check Duplicate (idempotent vs conflict)
             ↓
        Validate Quantity
             ↓
        Return result (for ApplyExecutionCommand generation)
    """

    def __init__(self) -> None:
        self._processed_reports: Dict[str, ExecutionReport] = {}
        self._order_executions: Dict[str, List[str]] = {}  # order_id → [execution_id]

    def handle(self, report: ExecutionReport,
               remaining_quantity: float = 0,
               original_quantity: float = 0,
               filled_quantity: float = 0) -> Dict:
        """Process an execution report.

        Args:
            report: The execution report to process.
            remaining_quantity: Current remaining quantity on the order.
            original_quantity: Original order quantity.
            filled_quantity: Current filled quantity on the order.

        Returns:
            Dict with processing result including whether to apply
            a fill command.

        Raises:
            ExecutionError: on conflicts or quantity exceeded.
        """
        # Check for duplicate execution_id
        if report.execution_id and report.execution_id in self._processed_reports:
            existing = self._processed_reports[report.execution_id]
            if self._reports_match(existing, report):
                # Idempotent replay
                return {
                    "status": "IDEMPOTENT_REPLAY",
                    "report": existing,
                    "action": "NONE",
                }
            else:
                raise ExecutionError(
                    f"Execution ID conflict: {report.execution_id} "
                    f"already processed with different payload",
                    order_id=report.order_id,
                    code="EXECUTION_ID_CONFLICT",
                )

        # Validate quantity for fills
        if report.is_fill:
            if report.executed_quantity <= 0:
                raise ExecutionError(
                    "Fill quantity must be positive",
                    order_id=report.order_id,
                    code="INVALID_FILL_QUANTITY",
                )
            if report.executed_quantity > remaining_quantity + 0.0001:
                raise ExecutionQuantityExceededError(
                    report.order_id,
                    requested=report.executed_quantity,
                    available=remaining_quantity,
                )

        # Store
        if report.execution_id:
            self._processed_reports[report.execution_id] = report
            if report.order_id not in self._order_executions:
                self._order_executions[report.order_id] = []
            self._order_executions[report.order_id].append(
                report.execution_id,
            )

        # Determine action
        if report.status == ExecutionStatus.PARTIALLY_FILLED:
            action = "APPLY_PARTIAL_FILL"
        elif report.status == ExecutionStatus.FILLED:
            action = "APPLY_FULL_FILL"
        elif report.status == ExecutionStatus.REJECTED:
            action = "REJECT_ORDER"
        elif report.status == ExecutionStatus.CANCELLED:
            action = "CONFIRM_CANCEL"
        else:
            action = "NONE"

        return {
            "status": "PROCESSED",
            "report": report,
            "action": action,
        }

    def is_processed(self, execution_id: str) -> bool:
        return execution_id in self._processed_reports

    def get_report(self, execution_id: str) -> Optional[ExecutionReport]:
        return self._processed_reports.get(execution_id)

    def get_order_executions(self, order_id: str) -> List[str]:
        return self._order_executions.get(order_id, [])

    @staticmethod
    def _reports_match(a: ExecutionReport,
                       b: ExecutionReport) -> bool:
        """Check if two reports have the same content."""
        return (
            a.execution_id == b.execution_id
            and a.order_id == b.order_id
            and a.status == b.status
            and a.executed_quantity == b.executed_quantity
            and a.executed_price == b.executed_price
        )
