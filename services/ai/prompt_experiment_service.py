"""
Prompt experiment service.
"""


class PromptExperimentService:

    def __init__(
        self,
        evaluator,
    ):

        self.evaluator = evaluator

    def compare(
        self,
        control_output,
        candidate_output,
    ):

        return {
            "control":
                self.evaluator.evaluate(
                    "control",
                    control_output,
                ),
            "candidate":
                self.evaluator.evaluate(
                    "candidate",
                    candidate_output,
                ),
        }