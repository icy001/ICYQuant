"""
Factor shock processor.
"""


class FactorShockProcessor:

    def apply(
        self,
        value,
        shock,
    ):

        return value * (
            1 + shock
        )