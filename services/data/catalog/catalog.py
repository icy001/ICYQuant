"""
Dataset catalog registry.
"""


class DatasetCatalog:
    def __init__(self):
        self.entries = []

    def register(
        self,
        dataset,
    ):
        self.entries.append(dataset)

    def list_all(
        self,
    ):
        return self.entries