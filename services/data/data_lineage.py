"""
Dataset lineage.
"""


class DataLineage:

    def __init__(self):

        self._graph = {}

    def register(
        self,
        child,
        parent,
    ):

        self._graph.setdefault(
            child,
            [],
        ).append(parent)

    def parents(
        self,
        dataset,
    ):

        return self._graph.get(
            dataset,
            [],
        )