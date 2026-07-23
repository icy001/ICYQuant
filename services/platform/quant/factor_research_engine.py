"""
Factor research engine.
"""


class FactorResearchEngine:

    def __init__(self):

        self.factors = []

    def register(
        self,
        factor,
    ):

        self.factors.append(factor)

    def research(self):

        return self.factors