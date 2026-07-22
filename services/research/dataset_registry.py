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

        self.datasets[
            dataset.dataset_id
        ] = dataset

    def get(
        self,
        dataset_id,
    ):

        return self.datasets.get(
            dataset_id
        )

    def list_all(self):

        return list(
            self.datasets.values()
        )