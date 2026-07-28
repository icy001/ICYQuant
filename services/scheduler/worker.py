class WorkerManager:

    def run(
        self,
        job
    ):
        job.status = "COMPLETED"

        return job
