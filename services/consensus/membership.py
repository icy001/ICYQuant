class ClusterMembership:
    def __init__(self):
        self.nodes = []

    def add(self, node):
        self.nodes.append(node)

    def members(self):
        return self.nodes
