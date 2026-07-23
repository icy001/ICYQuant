"""
Agent task scheduler.
"""


class TaskScheduler:

    def __init__(self):

        self.queue = []

    def submit(self, task):

        self.queue.append(task)

    def next(self):

        if not self.queue:

            return None

        return self.queue.pop(0)