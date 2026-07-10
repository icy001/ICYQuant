class PerShareCommission:

    def __init__(self, rate: float = 0.005):
        self.rate = rate

    def calculate(self, quantity: float) -> float:
        return abs(quantity) * self.rate