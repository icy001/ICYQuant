"""ExecutionGateway — boundary between OMS and Execution layer.

The gateway is the ONLY communication channel between OMS and Execution.
OMS never directly calls broker/venue APIs — all communication goes
through this gateway.

Key principles:
    1. OMS owns order lifecycle state.
    2. Execution owns execution facts.
    3. ACK does not mean fill.
    4. Cancel request does not mean cancellation.
    5. Timeout must not automatically become failure.
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional

from .execution_request import ExecutionRequest, CancelRequest
from .execution_response import ExecutionAck, CancelAck
from .execution_report import ExecutionReport
from .execution_status import ExecutionStatus
from .execution_error import (
    ExecutionTimeoutError,
    ExecutionUnknownError,
    RequestIdReuseConflictError,
)


class ExecutionGateway(ABC):
    """Abstract gateway to the execution layer."""

    @abstractmethod
    def submit(self, request: ExecutionRequest) -> ExecutionAck:
        """Submit an order to the execution layer.

        Returns an ExecutionAck. If the call times out, the gateway
        should raise ExecutionTimeoutError — the caller must NOT
        treat this as a failure.
        """

    @abstractmethod
    def cancel(self, request: CancelRequest) -> CancelAck:
        """Submit a cancel request."""

    @abstractmethod
    def query_status(self, order_id: str) -> ExecutionReport:
        """Query the current execution status of an order."""


class InMemoryExecutionGateway(ExecutionGateway):
    """In-memory gateway for testing.

    Records all submissions and allows configuration of responses.
    Supports simulated timeouts and configurable ACK/report sequences.
    """

    def __init__(self) -> None:
        self._submissions: Dict[str, ExecutionRequest] = {}
        self._acks: Dict[str, ExecutionAck] = {}
        self._cancel_requests: Dict[str, CancelRequest] = {}
        self._cancel_acks: Dict[str, CancelAck] = {}
        self._reports: Dict[str, List[ExecutionReport]] = {}
        self._status_queries: Dict[str, ExecutionReport] = {}

        self._submit_timeout: bool = False
        self._cancel_timeout: bool = False
        self._query_timeout: bool = False
        self._pending_acks: List[ExecutionAck] = []
        self._pending_reports: List[ExecutionReport] = []

    # ── Configuration ──────────────────────────────

    def configure_submit_timeout(self, timeout: bool = True) -> None:
        self._submit_timeout = timeout

    def configure_cancel_timeout(self, timeout: bool = True) -> None:
        self._cancel_timeout = timeout

    def queue_ack(self, ack: ExecutionAck) -> None:
        self._pending_acks.append(ack)

    def queue_report(self, report: ExecutionReport) -> None:
        self._pending_reports.append(report)

    def set_status_query_result(self, order_id: str,
                                report: ExecutionReport) -> None:
        self._status_queries[order_id] = report

    # ── Gateway operations ─────────────────────────

    def submit(self, request: ExecutionRequest) -> ExecutionAck:
        if self._submit_timeout:
            raise ExecutionTimeoutError(
                request.order_id, request.request_id, "SUBMISSION",
            )

        # Check for request_id reuse with different hash
        if request.request_id in self._submissions:
            existing = self._submissions[request.request_id]
            if existing.request_hash != request.request_hash:
                raise RequestIdReuseConflictError(
                    request.request_id, request.order_id,
                )
            # Idempotent replay — return original ACK
            return self._acks.get(request.request_id, ExecutionAck(
                request_id=request.request_id,
                order_id=request.order_id,
                status=ExecutionStatus.ACCEPTED,
            ))

        self._submissions[request.request_id] = request

        # Return queued ACK or default accept
        if self._pending_acks:
            ack = self._pending_acks.pop(0)
            ack.request_id = request.request_id
            ack.order_id = request.order_id
        else:
            ack = ExecutionAck.accepted(
                request_id=request.request_id,
                order_id=request.order_id,
                venue_order_id=f"VENUE-{len(self._submissions):06d}",
                correlation_id=request.correlation_id,
            )
        self._acks[request.request_id] = ack
        return ack

    def cancel(self, request: CancelRequest) -> CancelAck:
        if self._cancel_timeout:
            raise ExecutionTimeoutError(
                request.order_id, request.cancel_request_id, "CANCEL",
            )

        self._cancel_requests[request.cancel_request_id] = request
        ack = CancelAck.confirmed(
            cancel_request_id=request.cancel_request_id,
            order_id=request.order_id,
            cancelled_quantity=request.cancel_quantity,
            correlation_id=request.correlation_id,
        )
        self._cancel_acks[request.cancel_request_id] = ack
        return ack

    def query_status(self, order_id: str) -> ExecutionReport:
        if self._query_timeout:
            raise ExecutionTimeoutError(order_id, "", "QUERY")

        if order_id in self._status_queries:
            return self._status_queries[order_id]

        # Default: unknown
        return ExecutionReport(
            order_id=order_id,
            status=ExecutionStatus.UNKNOWN,
        )

    # ── Inspection ─────────────────────────────────

    @property
    def submission_count(self) -> int:
        return len(self._submissions)

    @property
    def cancel_count(self) -> int:
        return len(self._cancel_requests)

    def get_submission(self, request_id: str) -> Optional[ExecutionRequest]:
        return self._submissions.get(request_id)

    def get_ack(self, request_id: str) -> Optional[ExecutionAck]:
        return self._acks.get(request_id)
