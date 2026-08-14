from __future__ import annotations

from dataclasses import dataclass

from services.execution.domain.state import ExecutionState
from services.execution.domain.transition import (
    ExecutionTransition,
)


@dataclass
class ExecutionLifecycle:

    state: ExecutionState = ExecutionState.CREATED

    def transition(
        self,
        target: ExecutionState,
        *,
        reason: str | None = None,
    ) -> None:

        transition = ExecutionTransition(
            from_state=self.state,
            to_state=target,
            reason=reason,
        )

        transition.validate()

        self.state = target

    @property
    def terminal(self) -> bool:
        return self.state in {
            ExecutionState.FILLED,
            ExecutionState.CANCELLED,
            ExecutionState.REJECTED,
            ExecutionState.EXPIRED,
            ExecutionState.FAILED,
        }
