from services.job import *


def test_job():

    service = JobService(
        JobRepository(),
        JobQueue(),
        WorkerPool()
    )

    job = Job(
        "JOB001",
        "Settlement",
        JobStatus.CREATED,
        JobPriority.HIGH
    )

    service.submit(job)

    result = service.execute_next()

    assert result.status == JobStatus.SUCCESS
