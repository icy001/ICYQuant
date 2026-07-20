"""
Compliance alert model.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ComplianceAlert:
    severity: str
    message: str