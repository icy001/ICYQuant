"""
Market scenario generator.
"""


class ScenarioGenerator:

    def generate(
        self,
        assumptions,
    ):

        return {
            "scenario": assumptions,
            "probability": 0.5,
        }