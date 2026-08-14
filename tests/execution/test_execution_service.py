from services.execution.adapters.simulator import (
    SimulatorExecutionAdapter,
)
from services.execution.application.execution_service import (
    ExecutionService,
)
from services.execution.domain.adapter_result import (
    AdapterOrderStatus,
    AdapterSubmissionResult,
)
from services.execution.domain.lifecycle import (
    ExecutionLifecycle,
)
from services.execution.domain.request import (
    ExecutionOrderType,
    ExecutionRequest,
    ExecutionSide,
)
from services.execution.domain.state import (
    ExecutionState,
)


def build_request():
    return ExecutionRequest(
        request_id="exec-001",
        order_id="order-001",
        symbol="AAPL",
        side=ExecutionSide.BUY,
        order_type=ExecutionOrderType.MARKET,
        quantity=100,
    )


def test_execution_service_submit():

    adapter = SimulatorExecutionAdapter()

    service = ExecutionService(
        adapter
    )

    request = build_request()

    lifecycle = ExecutionLifecycle()

    result = service.submit(
        request,
        lifecycle,
    )

    assert result.status.value == "ACCEPTED"

    assert (
        lifecycle.state
        == ExecutionState.SUBMITTED
    )


def test_execution_service_rejects_business_rejection():

    class RejectingAdapter:
        def submit(self, request):
            return AdapterSubmissionResult(
                external_order_id="EXT-REJ",
                status=AdapterOrderStatus.REJECTED,
                message="insufficient margin",
            )

        def cancel(self, external_order_id):
            return None

        def get_status(self, external_order_id):
            return "REJECTED"

    service = ExecutionService(
        RejectingAdapter()
    )

    lifecycle = ExecutionLifecycle()

    result = service.submit(
        build_request(),
        lifecycle,
    )

    assert result.status == AdapterOrderStatus.REJECTED
    assert lifecycle.state == ExecutionState.REJECTED
    assert lifecycle.terminal


def test_execution_service_cancel_flow():

    adapter = SimulatorExecutionAdapter()
    service = ExecutionService(adapter)

    lifecycle = ExecutionLifecycle()
    result = service.submit(
        build_request(),
        lifecycle,
    )

    assert lifecycle.state == ExecutionState.SUBMITTED

    service.cancel(
        result.external_order_id,
        lifecycle,
    )

    assert lifecycle.state == ExecutionState.CANCELLED
    assert lifecycle.terminal
    assert (
        adapter.get_status(
            result.external_order_id
        )
        == "CANCELLED"
    )
