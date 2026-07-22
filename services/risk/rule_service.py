"""
Rule management service.
"""


class RuleService:

    def __init__(
        self,
        repository,
    ):

        self.repository = repository

    def register(
        self,
        rule,
    ):

        self.repository.save(
            rule,
        )