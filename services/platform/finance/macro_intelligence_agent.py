"""
Macro intelligence agent.
"""


class MacroIntelligenceAgent:

    def __init__(
        self,
        reasoning_engine,
    ):

        self.engine = reasoning_engine

    def analyze(
        self,
        data,
    ):

        return self.engine.analyze(
            data
        )