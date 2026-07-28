class JobRepository:

    def __init__(self):
        self.jobs = {}

    def save(
        self,
        job
    ):
        self.jobs[job.job_id] = job

    def get(
        self,
        job_id
    ):
        return self.jobs.get(job_id)
