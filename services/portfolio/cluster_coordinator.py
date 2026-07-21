"""
Portfolio cluster coordinator.
"""


class PortfolioClusterCoordinator:

    def __init__(
        self,
        repository,
        election,
    ):

        self.repository = repository

        self.election = election

    def leader(self):

        return self.election.elect(
            self.repository.list_nodes()
        )