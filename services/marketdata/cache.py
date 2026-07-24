class MarketDataCache:

    def __init__(self):
        self.data = {}

    def set(
        self,
        symbol,
        value
    ):
        self.data[symbol] = value

    def get(
        self,
        symbol
    ):
        return self.data.get(symbol)