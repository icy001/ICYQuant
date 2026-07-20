"""
Walk-forward result aggregator.
"""


class WalkForwardAggregator:
    def aggregate(
        self,
        results,
    ):
        return {
            "runs": len(results),
        }