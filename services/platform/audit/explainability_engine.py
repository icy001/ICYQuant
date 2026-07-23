"""
Investment explainability engine.
"""


class ExplainabilityEngine:

    def explain(
        self,
        decision,
    ):
        return {
            "decision":
                decision,
            "explanation":
                "generated"
        }