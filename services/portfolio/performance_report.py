"""
Performance report generator.
"""


class PerformanceReportGenerator:
    def generate(
        self,
        performance,
    ):
        return {
            "return": performance.get("return"),
            "alpha": performance.get("alpha"),
            "beta": performance.get("beta"),
        }