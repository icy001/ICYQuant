"""Execution gateway contract (Commit 33 Part 1.3 #9 / #29).

The :class:`ExecutionGateway` protocol is the *only* external execution entry
point.  The order engine never talks to REST / FIX / WebSocket / broker SDKs
directly; it always goes through this boundary, so switching between Paper,
Live, Backtest or different brokers never touches the order domain.
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from services.order.engine.execution.request import ExecutionRequest
from services.order.engine.execution.response import ExecutionResponse


@runtime_checkable
class ExecutionGateway(Protocol):
    """Stable contract between the order engine and the execution engine."""

    def submit(
        self,
        request: ExecutionRequest,
    ) -> ExecutionResponse: ...

    def cancel(
        self,
        request: ExecutionRequest,
    ) -> ExecutionResponse: ...

    def query(
        self,
        order_id: str,
    ) -> Optional[ExecutionResponse]: ...
