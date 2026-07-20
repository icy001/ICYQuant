"""
Experiment comparator.
"""

from .comparison import ExperimentComparison


class ExperimentComparator:
    def compare(
        self,
        left,
        right,
        metric,
    ):
        winner = (
            left.experiment_id
            if left.metrics[metric] >= right.metrics[metric]
            else right.experiment_id
        )

        return ExperimentComparison(
            left=left.experiment_id,
            right=right.experiment_id,
            metric=metric,
            winner=winner,
        )