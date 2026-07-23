"""
Distributed task queue.
"""

from queue import Queue


class DistributedTaskQueue:

    def __init__(self):

        self.queue = Queue()

    def submit(
        self,
        task,
    ):

        self.queue.put(task)

    def fetch(self):

        return self.queue.get()