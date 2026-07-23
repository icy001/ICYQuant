"""
Agent cluster manager.
"""


class ClusterManager:

    def __init__(self):

        self.nodes = {}

    def register(self, node):

        self.nodes[node.node_id] = node

    def unregister(self, node_id):

        self.nodes.pop(node_id, None)

    def healthy_nodes(self):

        return [
            n
            for n in self.nodes.values()
            if n.status == "healthy"
        ]