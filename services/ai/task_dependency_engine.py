"""
Task dependency resolver.
"""


class TaskDependencyEngine:

    def resolve(
        self,
        dag,
    ):

        result = []

        visited = set()

        def visit(node):

            if node in visited:

                return

            for dep in dag.dependencies(node):

                visit(dep)

            visited.add(node)

            result.append(node)

        for node in dag.nodes:

            visit(node)

        return result