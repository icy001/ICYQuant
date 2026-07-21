from services.portfolio import (
    ClusterNode,
    DistributedScheduler,
    JobQueue,
    LoadBalancer,
    SchedulerJob,
    TaskDispatcher,
)


def test_scheduler():
    queue = JobQueue()

    queue.submit(
        SchedulerJob(
            "JOB-001",
            "rebalance",
            {},
        )
    )

    scheduler = DistributedScheduler(
        queue,
        LoadBalancer(),
        TaskDispatcher(),
    )

    result = scheduler.schedule(
        [
            ClusterNode(
                "node-1",
                "10.0.0.1",
                "LEADER",
            )
        ]
    )

    assert result["job"] == "JOB-001"