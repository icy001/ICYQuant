"""
Investment decision attribution.
"""


class DecisionAttributionEngine:

    def attribute(
        self,
        decision,
        outcome,
    ):
        return {
            "decision":
                decision,
            "outcome":
                outcome,
            "source":
                "calculated"
        }