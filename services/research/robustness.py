"""
Robustness evaluation.
"""


class RobustnessEvaluator:
    def evaluate(
        self,
        summary,
    ):
        return {
            "robust": summary["runs"] > 0,
        }