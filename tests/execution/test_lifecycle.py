import pytest

from services.execution.domain.lifecycle import (
    ExecutionLifecycle,
)
from services.execution.domain.state import (
    ExecutionState,
)
from services.execution.domain.transition import (
    InvalidExecutionTransition,
)


def test_execution_lifecycle():

    lifecycle = ExecutionLifecycle()

    assert lifecycle.state == ExecutionState.CREATED

    lifecycle.transition(
        ExecutionState.READY
    )

    lifecycle.transition(
        ExecutionState.SUBMITTED
    )

    assert lifecycle.state == ExecutionState.SUBMITTED


def test_invalid_transition_is_rejected():

    lifecycle = ExecutionLifecycle()

    with pytest.raises(
        InvalidExecutionTransition
    ):
        lifecycle.transition(
            ExecutionState.FILLED
        )


def test_filled_is_terminal():

    lifecycle = ExecutionLifecycle(
        state=ExecutionState.FILLED
    )

    assert lifecycle.terminal


def test_cancelled_is_terminal():

    lifecycle = ExecutionLifecycle(
        state=ExecutionState.CANCELLED
    )

    assert lifecycle.terminal


@pytest.mark.parametrize(
    "state",
    [
        ExecutionState.REJECTED,
        ExecutionState.EXPIRED,
        ExecutionState.FAILED,
    ],
)
def test_other_terminal_states(state):

    lifecycle = ExecutionLifecycle(state=state)

    assert lifecycle.terminal


def test_partial_fill_progression_via_service():

    from services.execution.application.lifecycle_service import (
        ExecutionLifecycleService,
    )
    from services.execution.domain.result import (
        ExecutionResult,
    )

    lifecycle = ExecutionLifecycle()
    result = ExecutionResult(requested_quantity=1000)
    service = ExecutionLifecycleService()

    lifecycle.transition(ExecutionState.READY)
    service.submit(lifecycle)

    assert lifecycle.state == ExecutionState.SUBMITTED

    service.apply_fill(lifecycle, result, quantity=300, price=100)
    assert lifecycle.state == ExecutionState.PARTIALLY_FILLED
    assert result.filled_quantity == 300
    assert result.remaining_quantity == 700

    service.apply_fill(lifecycle, result, quantity=400, price=101)
    assert lifecycle.state == ExecutionState.PARTIALLY_FILLED
    assert result.filled_quantity == 700
    assert result.remaining_quantity == 300

    service.apply_fill(lifecycle, result, quantity=300, price=102)
    assert lifecycle.state == ExecutionState.FILLED
    assert result.filled_quantity == 1000
    assert result.remaining_quantity == 0
    assert result.fully_filled
    assert result.average_fill_price == 101
    assert lifecycle.terminal


def test_cancel_flow_via_service():

    from services.execution.application.lifecycle_service import (
        ExecutionLifecycleService,
    )

    lifecycle = ExecutionLifecycle(
        state=ExecutionState.SUBMITTED
    )
    service = ExecutionLifecycleService()

    service.cancel(lifecycle)
    assert lifecycle.state == ExecutionState.CANCEL_PENDING
    assert not lifecycle.terminal

    service.cancelled(lifecycle)
    assert lifecycle.state == ExecutionState.CANCELLED
    assert lifecycle.terminal
