"""
Slippage simulator.
"""


class SlippageModel:
    def calculate(
        self,
        price: float,
        side: str,
        rate: float = 0.0005,
    ):
        if side == "BUY":
            return price * (1 + rate)
        return price * (1 - rate)