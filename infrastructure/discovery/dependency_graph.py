"""
Service dependency graph.
"""


class DependencyGraph:

    def __init__(self):
        self.graph = {}

    def add_dependency(
        self,
        service,
        dependency,
    ):
        self.graph.setdefault(
            service,
            []
        ).append(
            dependency
        )

    def dependencies(
        self,
        service,
    ):
        return self.graph.get(
            service,
            []
        )