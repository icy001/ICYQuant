"""
Experiment registry.
"""

from .experiment import Experiment


class ExperimentRegistry:
    def __init__(self):
        self._experiments = {}

    def register(
        self,
        experiment: Experiment,
    ):
        self._experiments[experiment.experiment_id] = experiment

    def get(
        self,
        experiment_id: str,
    ):
        return self._experiments.get(experiment_id)