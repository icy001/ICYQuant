"""
Research dependency validator.
"""


class ResearchDependencyValidator:

    def validate(
        self,
        dependencies,
    ):

        return all(
            dependency
            is not None
            for dependency in dependencies
        )