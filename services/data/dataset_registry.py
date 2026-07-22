"""
Dataset registry.
"""


class DatasetRegistry:

    def __init__(self):

        self._datasets = {}

    def register(
        self,
        dataset,
    ):

        self._datasets[
            dataset.dataset_id
        ] = dataset

    def get(
        self,
        dataset_id,
    ):

        return self._datasets.get(
            dataset_id
        )

    def list_all(self):

        return list(
            self._datasets.values()
        )