"""
Task planner.
"""


class TaskPlanner:

    def plan(
        self,
        goal,
    ):

        return [
            {
                "step": 1,
                "task": goal.description,
            }
        ]