"""
Observability metrics.
"""


class ObservabilityMetrics:

    def snapshot(
        self,
        metrics,
    ):

        return {
            "count": len(metrics),
        }