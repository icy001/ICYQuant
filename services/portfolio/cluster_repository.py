"""
Cluster repository.
"""


class ClusterRepository:

    def __init__(self):

        self.nodes = {}

    def register(
        self,
        node,
    ):

        self.nodes[node.node_id] = node

    def list_nodes(self):

        return list(
            self.nodes.values()
        )