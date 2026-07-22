"""
Research workspace.
"""


class ResearchWorkspace:

    def __init__(
        self,
        project,
    ):

        self.project = project

        self.datasets = []

    def add_dataset(
        self,
        dataset,
    ):

        self.datasets.append(
            dataset
        )

    def list_datasets(self):

        return self.datasets