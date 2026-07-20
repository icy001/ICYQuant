"""
Report section.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ReportSection:
    title: str
    content: str