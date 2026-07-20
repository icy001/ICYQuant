"""
Experiment ranking.
"""


class ExperimentRanking:
    def rank(
        self,
        experiments,
        key,
    ):
        return sorted(experiments, key=key, reverse=True)