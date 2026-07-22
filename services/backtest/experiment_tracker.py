"""
Experiment tracker.
"""


class ExperimentTracker:

    def __init__(self):

        self.experiments = {}


    def track(
        self,
        experiment_id,
        metadata,
    ):

        self.experiments[
            experiment_id
        ] = metadata


    def get(
        self,
        experiment_id,
    ):

        return self.experiments.get(
            experiment_id
        )