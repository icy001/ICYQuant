from __future__ import annotations

from services.execution.domain.lifecycle import (
    ExecutionLifecycle,
)
from services.execution.domain.state import (
    ExecutionState,
)
from services.execution.ports.execution_adapter import (
    ExecutionAdapter,
)


class ExecutionService:

    def __init__(
        self,
        adapter: ExecutionAdapter,
    ) -> None:
        self._adapter = adapter

    def submit(
        self,
        request,
        lifecycle: ExecutionLifecycle,
    ):
        request.validate()

        lifecycle.transition(
            ExecutionState.READY
        )

        result = self._adapter.submit(
            request
        )

        if result.status.value == "REJECTED":
            lifecycle.transition(
                ExecutionState.REJECTED,
                reason=result.message,
            )
            return result

        lifecycle.transition(
            ExecutionState.SUBMITTED
        )

        return result

    def cancel(
        self,
        external_order_id: str,
        lifecycle: ExecutionLifecycle,
    ) -> None:

        lifecycle.transition(
            ExecutionState.CANCEL_PENDING
        )

        self._adapter.cancel(
            external_order_id
        )

        lifecycle.transition(
            ExecutionState.CANCELLED
        )
