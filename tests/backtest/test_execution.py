import pytest

from services.backtest import (
    StrategyRunner,
    VirtualOrderFactory,
    ExecutionFeedback,
    VirtualOrder,
    SlippageModel,
    CommissionModel,
    FillSimulator,
)


class DemoStrategy:
    def on_event(
        self,
        event,
    ):
        return event


@pytest.mark.asyncio
async def test_strategy_runner():
    runner = StrategyRunner()

    result = await runner.run(DemoStrategy(), "MARKET_EVENT")

    assert result == "MARKET_EVENT"


def test_virtual_order_factory():
    factory = VirtualOrderFactory()

    class Signal:
        symbol = "AAPL"
        side = "BUY"
        quantity = 100

    order = factory.create(Signal())

    assert order["symbol"] == "AAPL"
    assert order["side"] == "BUY"
    assert order["quantity"] == 100


def test_execution_feedback():
    feedback = ExecutionFeedback(order_id="order-001", status="FILLED")

    assert feedback.order_id == "order-001"
    assert feedback.status == "FILLED"


def test_fill_simulator():
    simulator = FillSimulator(
        SlippageModel(),
        CommissionModel(),
    )

    result = simulator.execute(
        VirtualOrder(
            "ORDER-001",
            "AAPL",
            "BUY",
            100,
            100.0,
        ),
        0.001,
        0.0005,
    )

    assert result.filled_quantity == 100
    assert result.average_price == 100.1