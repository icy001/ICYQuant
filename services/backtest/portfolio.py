class Portfolio:

    def __init__(self):

        self.cash = 0

        self.positions = {}

    def update(self, symbol, quantity):

        self.positions[symbol] = quantity
