"""
Comparison report.
"""


class ComparisonReport:
    def generate(
        self,
        comparisons,
    ):
        return {
            "count": len(comparisons),
            "comparisons": comparisons,
        }