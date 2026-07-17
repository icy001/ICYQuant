"""
Experiment storage.
"""


class ExperimentStore:
    def __init__(self):
        self.items = []

    def save(
        self,
        experiment,
    ):
        self.items.append(experiment)

    def list(self):
        return self.items