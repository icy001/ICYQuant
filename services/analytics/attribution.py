class AttributionEngine:
    def analyze(self, trades):
        result = {}

        for trade in trades:
            symbol = trade.symbol

            result[symbol] = (
                result.get(symbol, 0)
                +
                trade.quantity * trade.price
            )

        return result