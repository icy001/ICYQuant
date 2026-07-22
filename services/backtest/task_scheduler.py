"""
Distributed task scheduler.
"""


class TaskScheduler:

    def __init__(
        self,
        queue,
    ):

        self.queue = queue


    def schedule(
        self,
        task,
    ):

        self.queue.submit(
            task
        )


    def next_task(self):

        return self.queue.fetch()