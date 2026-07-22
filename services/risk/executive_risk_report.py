"""
Executive risk report generator.
"""


class ExecutiveRiskReportGenerator:

    def generate(
        self,
        summary,
    ):

        return {
            "overall_risk":
                summary.get(
                    "overall_risk"
                ),
            "top_risks":
                summary.get(
                    "top_risks"
                ),
            "recommendations":
                summary.get(
                    "recommendations"
                ),
        }