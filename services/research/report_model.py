"""
Research report model.
"""

from dataclasses import dataclass

from .report_section import ReportSection


@dataclass(frozen=True)
class SectionedResearchReport:
    title: str
    sections: list[ReportSection]