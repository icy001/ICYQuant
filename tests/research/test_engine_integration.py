import pytest

from services.research import (
    ResultCollector,
    OrderSimulator,
    ExecutionPipeline,
    IntegrationService,
    ExperimentContext,
)


def test_result_collector():
    collector = ResultCollector()

    result = collector.collect({"return": 0.12})

    assert result["return"] == 0.12


@pytest.mark.asyncio
async def test_order_simulator():
    simulator = OrderSimulator()

    order = {"symbol": "NVDA", "quantity": 100, "type": "market"}
    result = await simulator.submit(order)

    assert result["accepted"] is True
    assert result["order"] == order


@pytest.mark.asyncio
async def test_execution_pipeline():
    class MockMarketProvider:
        async def load(self, dataset):
            return {"loaded": True, "dataset": dataset}

    class MockEngineAdapter:
        async def execute(self, context):
            return {"executed": True}

    market_provider = MockMarketProvider()
    engine_adapter = MockEngineAdapter()
    pipeline = ExecutionPipeline(market_provider, engine_adapter)

    context = ExperimentContext(
        dataset="NASDAQ",
        parameter_version="v1",
        strategy_id="momentum",
    )

    result = await pipeline.run(context)

    assert result["executed"] is True


@pytest.mark.asyncio
async def test_integration_service():
    class MockPipeline:
        async def run(self, context):
            return {"pipeline_result": True}

    collector = ResultCollector()
    pipeline = MockPipeline()
    service = IntegrationService(pipeline, collector)

    result = await service.execute({"test": True})

    assert result["pipeline_result"] is True