"""
Adaptive execution planner.
"""


class AdaptiveExecutionPlanner:

    def plan(
        self,
        decision,
        context,
    ):

        return {
            "decision": decision,
            "context": context,
            "execution_mode": "adaptive",
        }