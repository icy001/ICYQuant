"""
Dependency resolver.
"""


class DependencyResolver:
    def ready(
        self,
        task_id,
        completed,
    ):
        return all(
            dependency in completed
            for dependency in completed.get(task_id, [])
        )