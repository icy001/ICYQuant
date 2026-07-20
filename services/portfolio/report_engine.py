"""
Portfolio reporting engine.
"""

from datetime import datetime

from .report import PortfolioReport


class PortfolioReportEngine:
    def __init__(
        self,
        generators,
    ):
        self.generators = generators

    def generate(
        self,
        report_type,
        data,
    ):
        generator = self.generators[report_type]
        content = generator.generate(data)

        return PortfolioReport(
            report_id="REPORT-" + datetime.utcnow().strftime("%Y%m%d%H%M%S"),
            report_type=report_type.value,
            created_at=datetime.utcnow(),
            content=content,
        )