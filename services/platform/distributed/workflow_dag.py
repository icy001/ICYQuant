"""
Workflow DAG scheduler.
"""


class WorkflowDAG:

    def __init__(self):

        self.graph = {}

    def add(
        self,
        task,
        depends_on=None,
    ):

        self.graph[task] = depends_on or []

    def tasks(self):

        return self.graph