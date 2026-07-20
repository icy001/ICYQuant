"""
Experiment repository.
"""


class ExperimentRepository:
    def __init__(self):
        self._experiments = {}

    def save(
        self,
        experiment,
    ):
        self._experiments[experiment.experiment_id] = experiment

    def get(
        self,
        experiment_id,
    ):
        return self._experiments.get(experiment_id)