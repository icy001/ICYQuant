from .worker import Worker


class WorkerPool:

    def __init__(self, size=4):
        self.workers = [
            Worker()
            for _ in range(size)
        ]

    def worker(self):
        return self.workers[0]
