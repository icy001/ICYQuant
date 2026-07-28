class DeadLetterQueue:

    def __init__(self):
        self.jobs = []

    def add(self, job):
        self.jobs.append(job)
