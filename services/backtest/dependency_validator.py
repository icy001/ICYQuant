"""
Dependency validator.
"""


class DependencyValidator:

    def validate(
        self,
        dependencies,
    ):

        return all(
            dependency
            is not None
            for dependency in dependencies
        )