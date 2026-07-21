"""
Query metrics.
"""


class QueryMetrics:

    def collect(
        self,
        duration,
    ):

        return {
            "latency_ms": duration,
        }