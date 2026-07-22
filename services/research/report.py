"""
Research report model.
"""

from dataclasses import dataclass
from datetime import datetime

from .report_section import ReportSection


@dataclass(frozen=True)
class ResearchReport:

    report_id: str = ""

    project_id: str = ""

    title: str = ""

    created_at: datetime = None

    content: dict = None

    sections: list = None

    def __post_init__(self):
        if self.created_at is None:
            object.__setattr__(self, "created_at", datetime.utcnow())
        if self.content is None:
            object.__setattr__(self, "content", {})
        if self.sections is None:
            object.__setattr__(self, "sections", [])


@dataclass(frozen=True)
class ComparisonReport:
    title: str = ""
    sections: list[ReportSection] = None

    def __post_init__(self):
        if self.sections is None:
            object.__setattr__(self, "sections", [])

    def generate(
        self,
        comparisons,
    ):
        return {
            "title": self.title,
            "comparisons": comparisons,
            "count": len(comparisons),
        }