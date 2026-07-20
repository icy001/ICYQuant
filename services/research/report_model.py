"""
Research report model.
"""

from dataclasses import dataclass

from .report_section import ReportSection


@dataclass(frozen=True)
class ResearchReport:
    title: str
    sections: list[ReportSection]