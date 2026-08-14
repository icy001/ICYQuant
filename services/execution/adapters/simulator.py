from __future__ import annotations

from uuid import uuid4

from services.execution.domain.adapter_result import (
    AdapterOrderStatus,
    AdapterSubmissionResult,
)
from services.execution.domain.request import (
    ExecutionRequest,
)
from services.execution.ports.execution_adapter import (
    ExecutionAdapter,
)


class SimulatorExecutionAdapter(ExecutionAdapter):
    """
    Local execution adapter for tests and paper trading.
    """

    def __init__(self) -> None:
        self._orders: dict[str, str] = {}

    def submit(
        self,
        request: ExecutionRequest,
    ) -> AdapterSubmissionResult:

        external_order_id = (
            f"SIM-{uuid4()}"
        )

        self._orders[
            external_order_id
        ] = "SUBMITTED"

        return AdapterSubmissionResult(
            external_order_id=external_order_id,
            status=AdapterOrderStatus.ACCEPTED,
        )

    def cancel(
        self,
        external_order_id: str,
    ) -> None:

        if external_order_id not in self._orders:
            raise KeyError(
                external_order_id
            )

        self._orders[
            external_order_id
        ] = "CANCELLED"

    def get_status(
        self,
        external_order_id: str,
    ) -> str:

        if external_order_id not in self._orders:
            raise KeyError(
                external_order_id
            )

        return self._orders[
            external_order_id
        ]
