"""
Risk reporting service.
"""


class RiskReportService:

    def __init__(
        self,
        engine,
    ):

        self.engine = engine

    def create(
        self,
        report_type,
        data,
    ):

        return self.engine.generate(
            report_type,
            data,
        )