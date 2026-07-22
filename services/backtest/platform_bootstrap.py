"""
Platform bootstrap.
"""


class PlatformBootstrap:

    def __init__(
        self,
        validator,
        checker,
    ):

        self.validator = validator

        self.checker = checker

    def initialize(
        self,
        dependencies,
        modules,
    ):

        if not self.validator.validate(
            dependencies,
        ):

            raise RuntimeError(
                "Dependency validation failed."
            )

        return self.checker.check(
            modules,
        )