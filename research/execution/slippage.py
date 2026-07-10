class PercentageSlippage:

    def __init__(self, rate: float = 0.0005):
        self.rate = rate

    def adjust(self, price: float, side: str) -> float:
        if side == "BUY":
            return price * (1 + self.rate)
        return price * (1 - self.rate)