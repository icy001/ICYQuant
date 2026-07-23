"""
Autonomous execution center.
"""


class AutonomousExecutionCenter:

    def __init__(
        self,
        planner,
        evaluator,
        correction,
        optimizer,
    ):

        self.planner = planner

        self.evaluator = evaluator

        self.correction = correction

        self.optimizer = optimizer

    def execute(
        self,
        decision,
        context,
    ):

        plan = self.planner.plan(
            decision,
            context,
        )

        result = {
            "plan": plan
        }

        evaluation = self.evaluator.evaluate(
            result
        )

        correction = self.correction.correct(
            evaluation
        )

        return {
            "evaluation": evaluation,
            "correction": correction,
        }