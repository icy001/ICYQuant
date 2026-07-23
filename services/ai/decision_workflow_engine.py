"""
Investment decision workflow engine.
"""


class DecisionWorkflowEngine:

    def __init__(
        self,
        supervisor,
    ):

        self.supervisor = supervisor

    def execute(
        self,
        workflow,
    ):

        results = {}

        for step in workflow:

            results[step["name"]] = (
                self.supervisor.dispatch(
                    step["agent"],
                    step["input"]
                )
            )

        return results