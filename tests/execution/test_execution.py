import pytest

from services.execution.service import ExecutionService
from services.execution.simulator import SimExecution
from services.oms.models import Order


class TestExecutionService:
    def test_execute_order(self):
        simulator = SimExecution()
        engine = ExecutionService(simulator)

        order = Order(
            symbol="NVDA",
            side="BUY",
            quantity=100,
            price=480.0,
        )

        fill = engine.execute_order(order)

        assert fill.order_id == order.order_id
        assert fill.symbol == "NVDA"
        assert fill.quantity == 100
        assert fill.price == 480.0