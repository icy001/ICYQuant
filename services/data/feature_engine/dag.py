"""
Feature dependency graph.
"""


class FeatureDAG:
    def __init__(self):
        self.nodes = {}

    def add(
        self,
        name,
        depends_on,
    ):
        self.nodes[name] = depends_on

    def dependencies(
        self,
        name,
    ):
        return self.nodes.get(name, [])