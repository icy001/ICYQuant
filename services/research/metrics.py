"""
Performance metrics.
"""


class PerformanceMetrics:
    def annual_return(
        self,
        total_return: float,
        years: float,
    ) -> float:
        return total_return / years