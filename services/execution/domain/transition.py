from __future__ import annotations

from dataclasses import dataclass

from services.execution.domain.state import ExecutionState


class InvalidExecutionTransition(ValueError):
    pass


_ALLOWED_TRANSITIONS = {
    ExecutionState.CREATED: {
        ExecutionState.READY,
        ExecutionState.REJECTED,
        ExecutionState.FAILED,
    },

    ExecutionState.READY: {
        ExecutionState.SUBMITTED,
        ExecutionState.REJECTED,
        ExecutionState.FAILED,
    },

    ExecutionState.SUBMITTED: {
        ExecutionState.PARTIALLY_FILLED,
        ExecutionState.FILLED,
        ExecutionState.CANCEL_PENDING,
        ExecutionState.REJECTED,
        ExecutionState.EXPIRED,
        ExecutionState.FAILED,
    },

    ExecutionState.PARTIALLY_FILLED: {
        ExecutionState.PARTIALLY_FILLED,
        ExecutionState.FILLED,
        ExecutionState.CANCEL_PENDING,
        ExecutionState.EXPIRED,
        ExecutionState.FAILED,
    },

    ExecutionState.CANCEL_PENDING: {
        ExecutionState.CANCELLED,
        ExecutionState.PARTIALLY_FILLED,
        ExecutionState.FILLED,
        ExecutionState.FAILED,
    },

    ExecutionState.FILLED: set(),
    ExecutionState.CANCELLED: set(),
    ExecutionState.REJECTED: set(),
    ExecutionState.EXPIRED: set(),
    ExecutionState.FAILED: set(),
}


@dataclass(frozen=True)
class ExecutionTransition:

    from_state: ExecutionState
    to_state: ExecutionState

    reason: str | None = None

    def validate(self) -> None:
        allowed = _ALLOWED_TRANSITIONS.get(
            self.from_state,
            set(),
        )

        if self.to_state not in allowed:
            raise InvalidExecutionTransition(
                f"Invalid execution transition: "
                f"{self.from_state.value} -> "
                f"{self.to_state.value}"
            )
