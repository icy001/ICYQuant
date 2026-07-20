"""
Report template.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ReportTemplate:
    name: str
    version: str