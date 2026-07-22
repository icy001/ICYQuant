"""
Daily risk report generator.
"""


class DailyRiskReportGenerator:

    def generate(
        self,
        risk_view,
    ):

        return {
            "risk_score":
                risk_view.get(
                    "risk_score"
                ),
            "metrics":
                risk_view.get(
                    "metrics"
                ),
            "alerts":
                risk_view.get(
                    "alerts"
                ),
        }