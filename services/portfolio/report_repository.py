"""
Report storage.
"""


class ReportRepository:
    def __init__(self):
        self.reports = []

    def save(
        self,
        report,
    ):
        self.reports.append(report)

    def list_all(self):
        return self.reports