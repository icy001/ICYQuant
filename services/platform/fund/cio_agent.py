"""
AI Chief Investment Officer Agent.
"""


class CIOAgent:

    def __init__(
        self,
        intelligence,
    ):
        self.intelligence = intelligence

    def decide(
        self,
        market_state,
    ):
        return {
            "decision":
                self.intelligence.analyze(
                    market_state
                )
        }