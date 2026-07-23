"""
Investment memory graph.
"""


class InvestmentMemoryGraph:

    def __init__(self):

        self.nodes = {}

        self.edges = []

    def add_memory(
        self,
        key,
        value,
    ):

        self.nodes[key] = value

    def connect(
        self,
        source,
        target,
    ):

        self.edges.append(
            (
                source,
                target
            )
        )

    def query(
        self,
        key,
    ):

        return self.nodes.get(key)