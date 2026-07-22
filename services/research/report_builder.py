"""
Research report builder.
"""

from datetime import datetime

from .report import ResearchReport
from .report_model import SectionedResearchReport


class ReportBuilder:

    def build(
        self,
        title,
        sections,
        project_id=None,
    ):

        return SectionedResearchReport(
            title=title,
            sections=sections,
        )

    def generate(
        self,
        title,
        sections,
    ):

        return self.build(title, sections)

    def create(
        self,
        project_id,
        title,
        content,
    ):

        return ResearchReport(
            report_id=
                "REPORT-" +
                datetime.utcnow().strftime(
                    "%Y%m%d%H%M%S"
                ),
            project_id=project_id,
            title=title,
            created_at=datetime.utcnow(),
            content=content,
        )