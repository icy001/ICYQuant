import pytest

from services.execution.adapters.simulator import (
    SimulatorExecutionAdapter,
)
from services.execution.application.adapter_registry import (
    ExecutionAdapterRegistry,
)


def test_register_and_get_adapter():

    registry = ExecutionAdapterRegistry()

    adapter = SimulatorExecutionAdapter()

    registry.register(
        "simulator",
        adapter,
    )

    assert (
        registry.get("simulator")
        is adapter
    )


def test_duplicate_registration_is_rejected():

    registry = ExecutionAdapterRegistry()

    registry.register(
        "simulator",
        SimulatorExecutionAdapter(),
    )

    with pytest.raises(ValueError):

        registry.register(
            "simulator",
            SimulatorExecutionAdapter(),
        )
