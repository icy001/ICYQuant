"""
Risk decision package.

Backward-compatible exports:

- ``RiskResult`` (legacy flat-module symbol, kept for compatibility)
"""

from __future__ import annotations

from dataclasses import dataclass

from ..enums import RiskDecision as EnumsRiskDecision
from .decision_record import RiskDecisionRecord
from .risk_decision import (
    RiskDecision,
    RiskDecisionStatus,
)


@dataclass(frozen=True)
class RiskResult:
    decision: EnumsRiskDecision
    reason: str | None = None


__all__ = [
    "RiskDecision",
    "RiskDecisionRecord",
    "RiskDecisionStatus",
    "RiskResult",
]
