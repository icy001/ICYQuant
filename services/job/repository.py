class JobRepository:

    def __init__(self):
        self.storage = {}

    def save(self, job):
        self.storage[job.job_id] = job

    def get(self, job_id):
        return self.storage.get(job_id)
