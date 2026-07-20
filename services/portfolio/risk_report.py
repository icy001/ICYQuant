"""
Risk report generator.
"""


class RiskReportGenerator:
    def generate(
        self,
        risk,
    ):
        return {
            "total_risk": risk.get("total_risk"),
            "exposure": risk.get("exposure"),
        }