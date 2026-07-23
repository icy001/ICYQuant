"""
Risk scenario simulator.
"""


class ScenarioSimulator:

    def simulate(
        self,
        portfolio,
        scenario,
    ):

        return {
            "portfolio": portfolio,
            "scenario": scenario,
            "impact": None,
        }