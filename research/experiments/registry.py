from typing import List

from .experiment import Experiment


class ExperimentRegistry:

    def __init__(self):
        self.experiments: List[Experiment] = []

    def register(self, experiment: Experiment):
        self.experiments.append(experiment)

    def list_all(self) -> List[Experiment]:
        return self.experiments

    def get_by_name(self, name: str) -> Experiment:
        for exp in self.experiments:
            if exp.metadata.name == name:
                return exp
        return None

    def __len__(self) -> int:
        return len(self.experiments)