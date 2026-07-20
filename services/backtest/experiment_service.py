"""
Experiment service.
"""


class ExperimentService:
    def __init__(
        self,
        repository,
    ):
        self.repository = repository

    def create(
        self,
        experiment,
    ):
        self.repository.save(experiment)
        return experiment