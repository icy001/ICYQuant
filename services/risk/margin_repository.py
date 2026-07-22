"""
Margin repository.
"""


class MarginRepository:

    def __init__(self):

        self.requirements = {}

    def save(
        self,
        requirement,
    ):

        self.requirements[
            requirement.symbol
        ] = requirement

    def load(
        self,
        symbol,
    ):

        return self.requirements.get(
            symbol
        )