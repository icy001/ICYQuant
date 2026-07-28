class Worker:

    def execute(self, job):
        job.status = "SUCCESS"

        return job
