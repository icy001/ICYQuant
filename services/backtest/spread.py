"""
Spread model.
"""


class SpreadModel:
    def calculate(
        self,
        price: float,
        spread: float = 0.0001,
    ):
        return price * spread