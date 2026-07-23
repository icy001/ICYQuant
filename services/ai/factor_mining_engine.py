"""
Automated factor mining engine.
"""


class FactorMiningEngine:

    def __init__(
        self,
        factor_library,
    ):

        self.factor_library = factor_library

    def mine(
        self,
        objective,
    ):

        factors = []

        for factor in self.factor_library:

            factors.append(
                {
                    "factor": factor,
                    "objective": objective,
                }
            )

        return factors