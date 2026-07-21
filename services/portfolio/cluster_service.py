"""
Cluster service.
"""


class ClusterService:

    def __init__(
        self,
        coordinator,
    ):

        self.coordinator = coordinator

    def leader(self):

        return self.coordinator.leader()