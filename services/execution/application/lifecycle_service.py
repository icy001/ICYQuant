from __future__ import annotations

from services.execution.domain.lifecycle import (
    ExecutionLifecycle,
)
from services.execution.domain.result import (
    ExecutionResult,
)
from services.execution.domain.state import (
    ExecutionState,
)


class ExecutionLifecycleService:

    def submit(
        self,
        lifecycle: ExecutionLifecycle,
    ) -> None:

        lifecycle.transition(
            ExecutionState.SUBMITTED
        )

    def apply_fill(
        self,
        lifecycle: ExecutionLifecycle,
        result: ExecutionResult,
        *,
        quantity: float,
        price: float,
    ) -> None:

        result.apply_fill(
            quantity=quantity,
            price=price,
        )

        if result.fully_filled:
            lifecycle.transition(
                ExecutionState.FILLED
            )
        else:
            lifecycle.transition(
                ExecutionState.PARTIALLY_FILLED
            )

    def cancel(
        self,
        lifecycle: ExecutionLifecycle,
    ) -> None:

        lifecycle.transition(
            ExecutionState.CANCEL_PENDING
        )

    def cancelled(
        self,
        lifecycle: ExecutionLifecycle,
    ) -> None:

        lifecycle.transition(
            ExecutionState.CANCELLED
        )
