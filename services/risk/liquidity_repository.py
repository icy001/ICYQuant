"""
Liquidity repository.
"""


class LiquidityRepository:

    def __init__(self):

        self.profiles = {}

    def save(
        self,
        profile,
    ):

        self.profiles[
            profile.symbol
        ] = profile

    def load(
        self,
        symbol,
    ):

        return self.profiles.get(
            symbol
        )