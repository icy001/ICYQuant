"""
Enterprise risk dashboard service.
"""


class RiskDashboardService:

    def build(
        self,
        report,
    ):

        return {
            "report_id":
                report.report_id,
            "type":
                report.report_type,
            "content":
                report.content,
        }