"""
Distributed portfolio state manager.
"""


class PortfolioStateManager:

    def __init__(
        self,
        repository,
        validator,
    ):

        self.repository = repository

        self.validator = validator

    def persist(
        self,
        state,
    ):

        if not self.validator.validate(
            state,
        ):

            raise ValueError(
                "Invalid state"
            )

        self.repository.save(
            state,
        )

        return state