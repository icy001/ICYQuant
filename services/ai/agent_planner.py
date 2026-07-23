"""
Agent task planner.
"""


class AgentPlanner:

    def plan(
        self,
        objective,
    ):

        return [
            {
                "step": 1,
                "action": objective,
            }
        ]