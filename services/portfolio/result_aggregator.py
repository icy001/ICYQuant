"""
Execution result aggregator.
"""


class ResultAggregator:

    def aggregate(
        self,
        results,
    ):

        return {
            "count": len(results),
            "results": results,
        }