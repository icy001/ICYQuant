"""
Dataset registry.
"""


class DatasetRegistry:
    def __init__(self):
        self.datasets = {}

    def register(
        self,
        dataset,
    ):
        self.datasets[dataset.name] = dataset

    def get(
        self,
        name,
    ):
        return self.datasets.get(name)