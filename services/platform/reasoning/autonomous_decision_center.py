"""
Autonomous decision center.
"""


class AutonomousDecisionCenter:

    def __init__(
        self,
        planner,
        reasoning,
        reflection,
    ):

        self.planner = planner

        self.reasoning = reasoning

        self.reflection = reflection

    def decide(
        self,
        goal,
    ):

        plan = self.planner.plan(goal)

        reasoning = self.reasoning.infer(plan)

        return self.reflection.review(reasoning)