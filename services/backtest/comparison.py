"""
Experiment comparison.
"""


class ExperimentComparator:
    def compare(
        self,
        results,
    ):
        return max(results, key=lambda x: x.return_rate)