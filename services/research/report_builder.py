"""
Research report builder.
"""

from .report_model import ResearchReport


class ReportBuilder:
    def build(
        self,
        title,
        sections,
    ):
        return ResearchReport(title=title, sections=sections)