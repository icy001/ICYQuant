"""
Query aggregator.
"""


class QueryAggregator:

    def aggregate(
        self,
        *results,
    ):

        merged = {}

        for result in results:

            if result:

                merged.update(result)

        return merged