"""
Rebalance order generator.
"""


class RebalanceOrderGenerator:
    def generate(
        self,
        requests,
    ):
        return [
            {
                "asset": request.asset,
                "direction": "BUY" if request.delta > 0 else "SELL",
            }
            for request in requests
        ]