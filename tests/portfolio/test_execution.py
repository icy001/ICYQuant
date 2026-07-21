from services.portfolio import (
    DistributedExecutionEngine,
    ExecutionTask,
    ResultAggregator,
    TaskExecutor,
)


def test_execution():
    engine = DistributedExecutionEngine(
        TaskExecutor(),
        ResultAggregator(),
    )

    result = engine.execute(
        [
            ExecutionTask(
                "TASK-001",
                "valuation",
                {"nav": 100},
            )
        ]
    )

    assert result["count"] == 1