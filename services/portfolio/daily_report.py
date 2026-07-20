"""
Daily portfolio report.
"""


class DailyReportGenerator:
    def generate(
        self,
        portfolio,
    ):
        return {
            "nav": portfolio.get("nav"),
            "return": portfolio.get("return"),
            "positions": portfolio.get("positions"),
        }