"""
Performance summary.
"""


class PerformanceSummary:
    def build(
        self,
        metrics: dict,
    ):
        return {
            "status": "COMPLETED",
            "metrics": metrics,
        }