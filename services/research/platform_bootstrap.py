"""
Research platform bootstrap.
"""


class ResearchPlatformBootstrap:

    def __init__(
        self,
        validator,
        health_checker,
    ):

        self.validator = validator
        self.health_checker = health_checker

    def initialize(
        self,
        dependencies,
        modules,
    ):

        if not self.validator.validate(
            dependencies,
        ):

            raise RuntimeError(
                "Research platform dependency validation failed."
            )

        return self.health_checker.check(
            modules,
        )