"""
Data lineage graph.
"""


class LineageGraph:
    def __init__(self):
        self.edges = {}

    def add_edge(
        self,
        source,
        target,
    ):
        self.edges.setdefault(source, []).append(target)

    def downstream(
        self,
        node,
    ):
        return self.edges.get(node, [])