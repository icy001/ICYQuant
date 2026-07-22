"""
Report exporter.
"""


class ReportExporter:

    def export(
        self,
        report,
        fmt="json",
    ):
        if hasattr(report, 'report_id') and report.report_id:
            return {
                "format": fmt,
                "report_id": report.report_id,
            }
        return report