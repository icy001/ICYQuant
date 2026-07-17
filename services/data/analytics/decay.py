"""
Factor decay monitor.
"""


class FactorDecayMonitor:
    def analyze(
        self,
        ic_series,
    ):
        if len(ic_series) < 2:
            return 0

        first = ic_series[0]
        last = ic_series[-1]

        return last - first