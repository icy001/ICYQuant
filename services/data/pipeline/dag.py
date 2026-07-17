"""
Pipeline DAG model.
"""


class PipelineDAG:
    def __init__(self):
        self.tasks = {}
        self.edges = {}

    def add_task(
        self,
        task,
    ):
        self.tasks[task.task_id] = task

    def add_dependency(
        self,
        upstream,
        downstream,
    ):
        self.edges.setdefault(upstream, []).append(downstream)