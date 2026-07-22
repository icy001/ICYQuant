"""
Backtest worker node.
"""

from .distributed_task import TaskStatus


class WorkerNode:

    def __init__(
        self,
        worker_id,
    ):

        self.worker_id = worker_id


    def execute(
        self,
        task,
        executor,
    ):

        task.status = TaskStatus.RUNNING

        result = executor(
            task.payload
        )

        task.status = TaskStatus.COMPLETED

        return result