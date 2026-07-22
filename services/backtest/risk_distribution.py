"""
Risk distribution analyzer.
"""


class RiskDistributionAnalyzer:

    def analyze(
        self,
        simulations,
    ):

        return [
            sum(path)
            for path in simulations
        ]