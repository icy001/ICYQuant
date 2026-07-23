"""
High availability coordinator.
"""


class HighAvailabilityCoordinator:

    def __init__(
        self,
        cluster,
        balancer,
    ):

        self.cluster = cluster

        self.balancer = balancer

    def schedule(self):

        nodes = self.cluster.healthy_nodes()

        return self.balancer.select(nodes)