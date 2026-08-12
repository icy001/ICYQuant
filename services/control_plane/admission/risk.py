"""
Risk adapter — the unified interface between Order Admission and any Risk
Engine implementation (spec section 7).

ICYQuant already has a Risk Engine; Order Admission does *not* re-implement
risk calculation.  This module defines the small, stable contract
(``RiskDecision`` / ``RiskResult``) that any engine can satisfy — either by
returning a ``RiskResult`` directly or by exposing a ``decision`` attribute —
so Admission and Risk stay decoupled.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RiskDecision(str, Enum):

    APPROVED = "APPROVED"

    REJECTED = "REJECTED"

    REDUCE_ONLY = "REDUCE_ONLY"


@dataclass(frozen=True)
class RiskResult:

    decision: RiskDecision

    reason: str = ""

    risk_score: float | None = None

    metadata: dict | None = None

    @classmethod
    def of(cls, decision: object, reason: str = "") -> "RiskResult":
        """Normalise any risk result to a ``RiskResult``.

        Accepts a ``RiskResult``, a ``RiskDecision`` or a plain string such as
        ``"APPROVED"`` (the shape used by the fake engines in tests).
        """
        raw = getattr(decision, "decision", decision)
        return cls(
            decision=RiskDecision(raw),
            reason=getattr(decision, "reason", "") or reason,
            risk_score=getattr(decision, "risk_score", None),
            metadata=getattr(decision, "metadata", None),
        )
