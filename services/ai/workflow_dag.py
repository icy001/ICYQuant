"""
AI workflow DAG.
"""


class WorkflowDAG:

    def __init__(self):

        self.nodes = {}

        self.edges = []

    def add_node(
        self,
        node,
    ):

        self.nodes[node.node_id] = node

    def add_edge(
        self,
        edge,
    ):

        self.edges.append(
            edge
        )

    def dependencies(
        self,
        node_id,
    ):

        return [
            edge.source
            for edge in self.edges
            if edge.target == node_id
        ]