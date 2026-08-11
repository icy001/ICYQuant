"""
Pre-Trade Context — Evaluation context for the pre-trade risk pipeline.

Carries the risk request, market data, account state, and policy
configuration through the rule chain evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from .risk_request import RiskRequest
from .risk_decision import RiskDecision
from .risk_reason import RiskReason


@dataclass
class PreTradeContext:
    """
    Mutable context that flows through the pre-trade risk pipeline.

    Accumulates results from each checker in the rule chain and
    provides shared access to market data, account state, and
    policy configuration.

    Usage::

        ctx = PreTradeContext(request=req)
        ctx.add_reason(reason)
        decision = ctx.build_decision()
    """

    # ---- Core Request ----
    request: RiskRequest

    # ---- Accumulated Results ----
    checker_results: dict[str, Any] = field(default_factory=dict)
    triggered_rules: list[str] = field(default_factory=list)
    passed_rules: list[str] = field(default_factory=list)
    reasons: list[RiskReason] = field(default_factory=list)
    risk_score: float = 0.0
    max_severity: str = "INFO"

    # ---- Pipeline State ----
    abort_early: bool = False
    abort_reason: Optional[str] = None

    # ---- Policy / Profile ----
    policy_overrides: dict[str, Any] = field(default_factory=dict)
    risk_profile: Optional[dict[str, Any]] = None
    account_state: dict[str, Any] = field(default_factory=dict)
    market_snapshot: dict[str, Any] = field(default_factory=dict)

    # ---- Metadata ----
    metadata: dict[str, Any] = field(default_factory=dict)

    # ---- Checker Result Management ----

    def add_checker_result(
        self,
        checker_name: str,
        passed: bool,
        rule_id: str = "",
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """Record a checker's evaluation result."""
        self.checker_results[checker_name] = {
            "passed": passed,
            "rule_id": rule_id,
            "metadata": metadata or {},
        }
        if passed:
            self.passed_rules.append(checker_name)
        else:
            self.triggered_rules.append(checker_name)

    def add_reason(self, reason: RiskReason) -> None:
        """Add a reason to the context (from checker warnings/failures)."""
        self.reasons.append(reason)
        # Track maximum severity
        severity_order = {"INFO": 0, "WARNING": 1, "BLOCKING": 2, "CRITICAL": 3}
        if (
            severity_order.get(reason.severity.value, 0)
            > severity_order.get(self.max_severity, 0)
        ):
            self.max_severity = reason.severity.value
        # Blocking/Critical reasons cause accumulation for risk_score
        if reason.severity.value in ("BLOCKING", "CRITICAL"):
            self.risk_score += 25  # 4 blocking = 100 max
        elif reason.severity.value == "WARNING":
            self.risk_score += 10

    # ---- Decision Building ----

    def build_decision(self) -> RiskDecision:
        """Build a RiskDecision from accumulated pipeline results."""
        risk_score = min(self.risk_score, 100.0)

        has_blocking = any(
            r.severity.value in ("BLOCKING", "CRITICAL") for r in self.reasons
        )

        if self.abort_early or has_blocking:
            return RiskDecision.rejected(
                request_id=self.request.request_id,
                risk_score=risk_score,
                triggered_rules=list(self.triggered_rules),
                reasons=[r.to_dict() for r in self.reasons],
                checker_results=dict(self.checker_results),
            )

        has_warnings = any(r.severity.value == "WARNING" for r in self.reasons)
        if has_warnings and risk_score >= 50:
            return RiskDecision.escalated(
                request_id=self.request.request_id,
                risk_score=risk_score,
                triggered_rules=list(self.triggered_rules),
                reasons=[r.to_dict() for r in self.reasons],
                checker_results=dict(self.checker_results),
            )

        return RiskDecision.approved(
            request_id=self.request.request_id,
            risk_score=risk_score,
            passed_rules=list(self.passed_rules),
            checker_results=dict(self.checker_results),
        )

    def should_continue(self) -> bool:
        """Check if pipeline should continue evaluating."""
        if self.abort_early:
            return False
        return not any(
            r.severity.value == "CRITICAL" for r in self.reasons
        )
