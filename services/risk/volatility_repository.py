"""
Volatility repository.
"""


class VolatilityRepository:

    def __init__(self):

        self.volatilities = {}

    def save(
        self,
        profile,
    ):

        self.volatilities[
            profile.symbol
        ] = profile

    def load(
        self,
        symbol,
    ):

        return self.volatilities.get(
            symbol
        )