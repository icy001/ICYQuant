"""
Risk validators.
"""

from __future__ import annotations

from .enums import RiskDecision
from .exceptions import RiskRejectedError


def ensure_approved(result):
    if result.decision != RiskDecision.APPROVE:
        raise RiskRejectedError(
            result.reason or "Risk rejected."
        )