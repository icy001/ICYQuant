"""
AI order decision agent.
"""


class OrderDecisionAgent:

    def decide(
        self,
        signal,
        risk,
    ):

        return {
            "signal":
                signal,
            "risk":
                risk,
            "approved":
                True,
        }