"""
Portfolio rebalancing engine.
"""


class RebalancingEngine:

    def rebalance(
        self,
        current,
        target,
    ):

        return {
            "current":
                current,
            "target":
                target,
            "action":
                "rebalance",
        }