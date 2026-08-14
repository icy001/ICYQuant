"""Risk decision domain model (Commit 37 Part 1.5).

``RiskDecisionStatus`` enumerates the four possible gate outcomes;
``RiskDecision`` is the immutable value object produced by every risk rule
and consumed by the ``RiskDecisionAggregator``. Factory methods
(``allow`` / ``reject`` / ``reduce`` / ``review``) keep construction explicit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RiskDecisionStatus(str, Enum):
    ALLOW = "ALLOW"
    REJECT = "REJECT"
    REDUCE = "REDUCE"
    REVIEW = "REVIEW"


@dataclass(frozen=True)
class RiskDecision:
    status: RiskDecisionStatus

    accepted_quantity: float | None = None

    reasons: tuple[str, ...] = ()

    triggered_rules: tuple[str, ...] = ()

    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def allowed(self) -> bool:
        return self.status == RiskDecisionStatus.ALLOW

    @property
    def rejected(self) -> bool:
        return self.status == RiskDecisionStatus.REJECT

    @property
    def requires_review(self) -> bool:
        return self.status == RiskDecisionStatus.REVIEW

    @property
    def reduced(self) -> bool:
        return self.status == RiskDecisionStatus.REDUCE

    @classmethod
    def allow(
        cls,
        *,
        quantity: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "RiskDecision":
        return cls(
            status=RiskDecisionStatus.ALLOW,
            accepted_quantity=quantity,
            metadata=metadata or {},
        )

    @classmethod
    def reject(
        cls,
        *,
        reason: str,
        rule: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "RiskDecision":
        return cls(
            status=RiskDecisionStatus.REJECT,
            reasons=(reason,),
            triggered_rules=(rule,) if rule else (),
            metadata=metadata or {},
        )

    @classmethod
    def reduce(
        cls,
        *,
        quantity: float,
        reason: str,
        rule: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "RiskDecision":
        return cls(
            status=RiskDecisionStatus.REDUCE,
            accepted_quantity=quantity,
            reasons=(reason,),
            triggered_rules=(rule,) if rule else (),
            metadata=metadata or {},
        )

    @classmethod
    def review(
        cls,
        *,
        reason: str,
        rule: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "RiskDecision":
        return cls(
            status=RiskDecisionStatus.REVIEW,
            reasons=(reason,),
            triggered_rules=(rule,) if rule else (),
            metadata=metadata or {},
        )
