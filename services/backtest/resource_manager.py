"""
Cluster resource manager.
"""


class ResourceManager:

    def __init__(self):

        self.workers = {}


    def register(
        self,
        worker,
    ):

        self.workers[
            worker.worker_id
        ] = worker


    def list_workers(self):

        return list(
            self.workers.values()
        )