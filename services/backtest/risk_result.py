"""
Risk evaluation result.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RiskResult:
    approved: bool
    reason: Optional[str]