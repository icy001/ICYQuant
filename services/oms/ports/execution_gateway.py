"""ExecutionGateway port — boundary between OMS and Execution layer.

OMS and Execution do NOT share internal domain models. They communicate
through this gateway using execution requests and results.

Key principle:
    - OMS owns the order lifecycle.
    - Execution owns the execution lifecycle.
    - The gateway translates between them.
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

from services.oms.domain.order import Order
from services.oms.domain.order_status import OrderStatus


class ExecutionStatus(Enum):
    """Status of an execution request."""

    SUBMITTED = auto()
    ACCEPTED = auto()
    PARTIAL_FILL = auto()
    FILLED = auto()
    CANCELLED = auto()
    REJECTED = auto()
    TIMEOUT = auto()
    UNKNOWN = auto()

    @property
    def is_terminal(self) -> bool:
        return self in (
            ExecutionStatus.FILLED,
            ExecutionStatus.CANCELLED,
            ExecutionStatus.REJECTED,
        )

    @property
    def is_unknown(self) -> bool:
        return self in (ExecutionStatus.TIMEOUT, ExecutionStatus.UNKNOWN)


@dataclass
class ExecutionResult:
    """Result returned by the execution gateway."""

    execution_id: str = ""
    status: ExecutionStatus = ExecutionStatus.UNKNOWN
    fill_quantity: float = 0.0
    fill_price: float = 0.0
    remaining_quantity: float = 0.0
    timestamp: float = field(default_factory=lambda: __import__("time").time())
    reason: str = ""
    raw_response: Optional[dict] = None


class ExecutionGateway(ABC):
    """Abstract gateway to the execution layer."""

    @abstractmethod
    def submit(self, order: Order) -> ExecutionResult:
        """Submit an order to the execution layer.

        Returns an ExecutionResult. If the call times out or the
        result is ambiguous, status should be UNKNOWN/TIMEOUT —
        NOT REJECTED. This preserves the invariant that unknown
        execution results must not be treated as failure.
        """

    @abstractmethod
    def cancel(self, order_id: str) -> ExecutionResult:
        """Request cancellation of a submitted order."""

    @abstractmethod
    def query_status(self, order_id: str) -> ExecutionResult:
        """Query the current execution status of an order."""


class InMemoryExecutionGateway(ExecutionGateway):
    """In-memory gateway for testing.

    Records all submissions and allows configuration of responses.
    """

    def __init__(self) -> None:
        self._submissions: dict = {}
        self._next_id: int = 1
        self._should_timeout: bool = False
        self._fill_responses: dict = {}

    def configure_fill(self, order_id: str,
                       fill_quantity: float,
                       fill_price: float) -> None:
        self._fill_responses[order_id] = (fill_quantity, fill_price)

    def configure_timeout(self, should_timeout: bool = True) -> None:
        self._should_timeout = should_timeout

    def submit(self, order: Order) -> ExecutionResult:
        if self._should_timeout:
            return ExecutionResult(
                execution_id=f"EXEC-TIMEOUT-{self._next_id}",
                status=ExecutionStatus.TIMEOUT,
                reason="Gateway timeout",
            )

        exec_id = f"EXEC-{self._next_id:06d}"
        self._next_id += 1

        if order.order_id.order_id in self._fill_responses:
            qty, price = self._fill_responses[order.order_id.order_id]
            return ExecutionResult(
                execution_id=exec_id,
                status=ExecutionStatus.FILLED,
                fill_quantity=qty,
                fill_price=price,
                remaining_quantity=order.quantity.original - qty,
            )

        self._submissions[order.order_id.order_id] = exec_id
        return ExecutionResult(
            execution_id=exec_id,
            status=ExecutionStatus.ACCEPTED,
            remaining_quantity=order.quantity.original,
        )

    def cancel(self, order_id: str) -> ExecutionResult:
        return ExecutionResult(
            execution_id=f"EXEC-CANCEL-{self._next_id:06d}",
            status=ExecutionStatus.CANCELLED,
            reason="Cancel confirmed",
        )

    def query_status(self, order_id: str) -> ExecutionResult:
        if order_id in self._submissions:
            return ExecutionResult(
                execution_id=self._submissions[order_id],
                status=ExecutionStatus.ACCEPTED,
            )
        return ExecutionResult(
            status=ExecutionStatus.UNKNOWN,
            reason="Order not found in execution layer",
        )

    @property
    def submission_count(self) -> int:
        return len(self._submissions)
