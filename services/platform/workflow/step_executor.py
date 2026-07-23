"""
Workflow step executor.
"""


class StepExecutor:

    def execute(
        self,
        step,
        context,
    ):

        return {
            "step": step,
            "status": "SUCCESS",
            "context": context,
        }