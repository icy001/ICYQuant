"""
Slippage model.
"""


class SlippageModel:

    def calculate(
        self,
        price,
        rate,
    ):
        return price * rate