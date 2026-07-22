"""
Risk dashboard backend.
"""


class RiskDashboard:

    def build(
        self,
        risk_view,
    ):

        return {
            "score":
                risk_view.risk_score,
            "metrics":
                risk_view.metrics,
        }