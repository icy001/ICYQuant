from .status import JobStatus


class JobService:

    def __init__(
        self,
        repository,
        queue,
        pool
    ):
        self.repository = repository
        self.queue = queue
        self.pool = pool

    def submit(self, job):
        job.status = JobStatus.QUEUED
        self.repository.save(job)
        self.queue.push(job)

    def execute_next(self):
        job = self.queue.pop()
        worker = self.pool.worker()

        return worker.execute(job)
