from services.scheduler import *


def test_scheduler():

    service = SchedulerService(
        JobRepository(),
        SchedulerEngine(
            WorkerManager()
        )
    )

    result = service.submit(
        Job(
            "JOB001",
            "DAILY_SETTLEMENT",
            "settlement",
            "CREATED"
        )
    )

    assert result.status == "COMPLETED"
