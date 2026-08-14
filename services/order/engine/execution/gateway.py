"""Execution gateway implementations (Commit 33 Part 1.3).

Production adapters (FIX / broker REST / exchange gateway) implement the
:class:`~services.order.engine.execution.contract.ExecutionGateway` protocol.
This module ships the :class:`FakeExecutionGateway` used for tests, paper
trading and simulation: it can simulate ACCEPTED / REJECTED / PENDING /
UNKNOWN / TIMEOUT / UNAVAILABLE without touching a real venue.
"""

from __future__ import annotations

from typing import Dict, Optional

from services.order.engine.execution.contract import ExecutionGateway
from services.order.engine.execution.errors import (
    ExecutionTimeoutError,
    ExecutionUnavailableError,
)
from services.order.engine.execution.request import ExecutionRequest
from services.order.engine.execution.response import (
    ExecutionResponse,
    ExecutionResponseStatus,
)


class FakeExecutionGateway:
    """In-memory execution gateway for tests / paper trading.

    Behaviour switches:

    * ``default_response`` - fixed answer for every submit; when unset the
      gateway answers ACCEPTED with a generated venue order id
    * ``fail_on_submit`` / ``fail_on_cancel`` - raise
      :class:`ExecutionUnavailableError` (fail-closed)
    * ``timeout_on_submit`` / ``timeout_on_cancel`` - raise
      :class:`ExecutionTimeoutError` (never a fake rejection)

    Idempotency: submitting the same ``execution_request_id`` twice replays
    the stored response and never sends the order to the venue a second time
    (Commit 33 Part 1.3 #21 / #35).
    """

    def __init__(
        self,
        *,
        default_response: Optional[ExecutionResponse] = None,
    ) -> None:
        self.default_response = default_response
        self.fail_on_submit = False
        self.fail_on_cancel = False
        self.timeout_on_submit = False
        self.timeout_on_cancel = False

        self._responses: Dict[str, ExecutionResponse] = {}
        self._cancel_responses: Dict[str, ExecutionResponse] = {}
        self._order_responses: Dict[str, ExecutionResponse] = {}
        self._venue_counter = 0

    # --- submit ------------------------------------------------------------

    def submit(self, request: ExecutionRequest) -> ExecutionResponse:
        if self.fail_on_submit:
            raise ExecutionUnavailableError("execution gateway unavailable")
        if self.timeout_on_submit:
            raise ExecutionTimeoutError("execution gateway timed out")

        key = request.execution_request_id
        if key in self._responses:
            return self._responses[key]  # idempotent replay, no re-send

        response = self.default_response
        if response is None:
            self._venue_counter += 1
            response = ExecutionResponse(
                execution_request_id=key,
                order_id=request.order_id,
                status=ExecutionResponseStatus.ACCEPTED,
                venue_order_id=f"VENUE-{self._venue_counter:06d}",
                reject_reason=None,
                timestamp=request.timestamp,
                correlation_id=request.correlation_id,
            )
        self._responses[key] = response
        self._order_responses[request.order_id] = response
        return response

    def submission_count(self, execution_request_id: str) -> int:
        """How many times the request was really sent to the venue."""
        return 1 if execution_request_id in self._responses else 0

    # --- cancel ------------------------------------------------------------

    def cancel(self, request: ExecutionRequest) -> ExecutionResponse:
        if self.fail_on_cancel:
            raise ExecutionUnavailableError("execution gateway unavailable")
        if self.timeout_on_cancel:
            raise ExecutionTimeoutError("execution gateway timed out")

        key = request.execution_request_id
        if key in self._cancel_responses:
            return self._cancel_responses[key]

        response = ExecutionResponse(
            execution_request_id=key,
            order_id=request.order_id,
            status=ExecutionResponseStatus.ACCEPTED,
            venue_order_id=self._venue_for(request.order_id),
            reject_reason=None,
            timestamp=request.timestamp,
            correlation_id=request.correlation_id,
        )
        self._cancel_responses[key] = response
        self._order_responses[request.order_id] = response
        return response

    # --- query -------------------------------------------------------------

    def query(self, order_id: str) -> Optional[ExecutionResponse]:
        return self._order_responses.get(order_id)

    def _venue_for(self, order_id: str) -> Optional[str]:
        response = self._order_responses.get(order_id)
        if response is None:
            return None
        return response.venue_order_id
