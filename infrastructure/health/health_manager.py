"""
Central health management.
"""


class HealthManager:

    def __init__(
        self,
        checker,
    ):
        self.checker = checker

    def inspect(
        self,
        services,
    ):
        return [
            self.checker.check(service)
            for service in services
        ]