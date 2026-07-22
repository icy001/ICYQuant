from services.backtest import (
    DistributedTask,
    JobQueue,
    WorkerNode,
    TaskScheduler,
    ResultAggregator,
    ResourceManager,
    DistributedBacktestEngine,
)


def test_distributed_engine():

    queue = JobQueue()

    scheduler = TaskScheduler(
        queue
    )

    scheduler.schedule(
        DistributedTask(
            "TASK-1",
            "WF-1",
            {
                "value": 1,
            },
        )
    )

    manager = ResourceManager()

    manager.register(
        WorkerNode(
            "worker-1",
        )
    )

    engine = DistributedBacktestEngine(
        scheduler,
        manager,
        ResultAggregator(),
    )

    result = engine.run(
        lambda payload: payload["value"]
    )

    assert result == [1]