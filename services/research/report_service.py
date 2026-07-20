"""
Research report service.
"""

from .report_builder import ReportBuilder


class ReportService:
    def __init__(
        self,
        builder,
    ):
        self.builder = builder

    def generate(
        self,
        title,
        sections,
    ):
        return self.builder.build(title, sections)