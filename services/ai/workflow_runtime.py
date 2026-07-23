"""
Workflow runtime.
"""


class WorkflowRuntime:

    def __init__(
        self,
        dependency_engine,
    ):

        self.dependency_engine = dependency_engine

    def execute(
        self,
        dag,
    ):

        return self.dependency_engine.resolve(
            dag
        )