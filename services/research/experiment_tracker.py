"""
Experiment tracker.
"""


class ExperimentTracker:

    def __init__(self):

        self._experiments = {}

    def log(
        self,
        experiment,
        metrics,
    ):

        self._experiments[
            experiment.experiment_id
        ] = {
            "experiment": experiment,
            "metrics": metrics,
        }

    def get(
        self,
        experiment_id,
    ):

        return self._experiments.get(
            experiment_id
        )

    def list_all(self):

        return list(
            self._experiments.values()
        )