"""
Dataset lineage tracking.
"""


class DataLineage:
    def __init__(self):
        self.graph = {}

    def add_relation(
        self,
        source,
        target,
    ):
        self.graph.setdefault(source, []).append(target)

    def downstream(
        self,
        source,
    ):
        return self.graph.get(source, [])