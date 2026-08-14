import pytest

from services.execution.adapters.simulator import (
    SimulatorExecutionAdapter,
)
from services.execution.domain.request import (
    ExecutionOrderType,
    ExecutionRequest,
    ExecutionSide,
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


def test_simulator_submit():

    adapter = SimulatorExecutionAdapter()

    result = adapter.submit(
        build_request()
    )

    assert result.external_order_id.startswith(
        "SIM-"
    )

    assert result.status.value == "ACCEPTED"


def test_simulator_cancel():

    adapter = SimulatorExecutionAdapter()

    result = adapter.submit(
        build_request()
    )

    adapter.cancel(
        result.external_order_id
    )

    assert (
        adapter.get_status(
            result.external_order_id
        )
        == "CANCELLED"
    )


def test_simulator_tracks_submitted_status():

    adapter = SimulatorExecutionAdapter()

    result = adapter.submit(
        build_request()
    )

    assert (
        adapter.get_status(
            result.external_order_id
        )
        == "SUBMITTED"
    )


def test_simulator_get_status_unknown_order_raises():

    adapter = SimulatorExecutionAdapter()

    with pytest.raises(KeyError):
        adapter.get_status(
            "SIM-does-not-exist"
        )


def test_simulator_cancel_unknown_order_raises():

    adapter = SimulatorExecutionAdapter()

    with pytest.raises(KeyError):
        adapter.cancel(
            "SIM-does-not-exist"
        )
