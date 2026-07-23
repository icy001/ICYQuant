"""
Workflow engine.
"""


class WorkflowEngine:

    def __init__(
        self,
        executor,
    ):

        self.executor = executor

    def run(
        self,
        workflow,
        context,
    ):

        results = []

        for step in workflow.steps:

            results.append(
                self.executor.execute(
                    step,
                    context,
                )
            )

        return results