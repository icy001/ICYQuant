"""
Agent runtime.
"""


class AgentRuntime:

    def __init__(
        self,
        planner,
        executor,
    ):

        self.planner = planner

        self.executor = executor

    def run(
        self,
        objective,
    ):

        plan = self.planner.plan(
            objective
        )

        results = []

        for step in plan:

            results.append(
                step
            )

        return results