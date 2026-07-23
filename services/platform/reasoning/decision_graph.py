"""
Decision graph.
"""


class DecisionGraph:

    def __init__(self):

        self.nodes = []

        self.edges = []

    def add_node(self, node):

        self.nodes.append(node)

    def add_edge(
        self,
        source,
        target,
    ):

        self.edges.append(
            (source, target)
        )