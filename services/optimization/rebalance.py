class RebalanceEngine:
    def rebalance(self, current, target):
        changes = {}

        for symbol, weight in target.items():
            changes[symbol] = (
                weight -
                current.get(symbol, 0)
            )

        return changes