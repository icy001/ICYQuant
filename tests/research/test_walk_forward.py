import pytest

from services.research import (
    WindowGenerator,
    WalkForwardAggregator,
    RobustnessEvaluator,
    WalkForwardService,
    WalkForwardWindow,
)


def test_window_generator():
    generator = WindowGenerator()

    windows = generator.generate()

    assert len(windows) == 1


def test_walk_forward_window():
    window = WalkForwardWindow(
        train_start="2023-01",
        train_end="2023-06",
        test_start="2023-07",
        test_end="2023-09",
    )

    assert window.train_start == "2023-01"
    assert window.test_end == "2023-09"


def test_aggregation():
    aggregator = WalkForwardAggregator()

    result = aggregator.aggregate([1, 2, 3])

    assert result["runs"] == 3


def test_robustness_evaluator():
    evaluator = RobustnessEvaluator()

    summary = {"runs": 5}
    result = evaluator.evaluate(summary)

    assert result["robust"] is True


def test_walk_forward_service():
    aggregator = WalkForwardAggregator()
    service = WalkForwardService(aggregator)

    results = [1, 2, 3, 4, 5]
    summary = service.summarize(results)

    assert summary["runs"] == 5


@pytest.mark.asyncio
async def test_walk_forward_executor():
    from services.research import WalkForwardExecutor

    executor = WalkForwardExecutor()

    class MockRunner:
        async def run(self, window):
            return {"window": window.train_start}

    windows = [
        WalkForwardWindow("2023-01", "2023-06", "2023-07", "2023-09"),
        WalkForwardWindow("2023-04", "2023-09", "2023-10", "2023-12"),
    ]

    results = await executor.execute(windows, MockRunner())

    assert len(results) == 2