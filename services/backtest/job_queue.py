"""
Distributed job queue.
"""

from collections import deque


class JobQueue:

    def __init__(self):

        self._queue = deque()


    def submit(
        self,
        task,
    ):

        self._queue.append(
            task
        )


    def fetch(self):

        if not self._queue:

            return None

        return self._queue.popleft()


    def size(self):

        return len(
            self._queue
        )