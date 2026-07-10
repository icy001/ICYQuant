class FixedSpread:

    def __init__(self, spread: float):
        self.spread = spread

    def adjust_price(self, price: float, side: str) -> float:
        if side == "BUY":
            return price + self.spread / 2
        return price - self.spread / 2