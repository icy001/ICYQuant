"""
Research report template.
"""

from dataclasses import dataclass
from enum import Enum


class ReportTemplateType(Enum):

    FACTOR = "FACTOR"

    ALPHA = "ALPHA"

    EXPERIMENT = "EXPERIMENT"

    STRATEGY = "STRATEGY"


@dataclass(frozen=True)
class ReportTemplate:
    name: str
    version: str