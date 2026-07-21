"""
Distributed job queue.
"""


class JobQueue:

    def __init__(self):

        self.jobs = []

    def submit(self, job):

        self.jobs.append(job)

    def next_job(self):

        if not self.jobs:

            return None

        return self.jobs.pop(0)