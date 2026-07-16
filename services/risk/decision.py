"""
Risk decision model.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .enums import RiskDecision


@dataclass(frozen=True)
class RiskResult:
    decision: RiskDecision
    reason: Optional[str] = None