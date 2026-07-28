class JobQueue:

    def __init__(self):
        self.jobs = []

    def push(self, job):
        self.jobs.append(job)

    def pop(self):
        return self.jobs.pop(0)
