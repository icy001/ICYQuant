"""
Research report model.
"""

from dataclasses import dataclass, field


@dataclass
class ResearchReport:

    report_id: str

    title: str

    summary: str

    findings: list = field(default_factory=list)

    metadata: dict = field(default_factory=dict)