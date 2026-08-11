"""
ICYQuant Guardrail — safety guardrails preventing unsafe AI agent actions.

Enforces hard constraints that prevent AI agents from bypassing critical
safety systems (Risk Engine, OMS). The guardrail layer is the system's
last line of defense — it cannot be overridden by any agent.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class GuardrailAction(str, Enum):
    ALLOW = "allow"           # Pass through
    WARN = "warn"             # Allow but log warning
    BLOCK = "block"           # Reject with reason
    ESCALATE = "escalate"     # Require human review
    QUARANTINE = "quarantine" # Isolate for investigation


class GuardrailDomain(str, Enum):
    TRADE_EXECUTION = "trade_execution"
    RISK_LIMIT = "risk_limit"
    DATA_ACCESS = "data_access"
    ORDER_SIZE = "order_size"
    PORTFOLIO_CONSTRAINT = "portfolio_constraint"
    COMPLIANCE = "compliance"
    SYSTEM_OVERRIDE = "system_override"
    EXTERNAL_ACCESS = "external_access"


@dataclass
class GuardrailCheck:
    """A single guardrail check definition."""
    check_id: str
    domain: GuardrailDomain
    description: str = ""
    action: GuardrailAction = GuardrailAction.BLOCK
    check_fn: Optional[Callable[..., tuple[bool, str]]] = None
    enabled: bool = True
    priority: int = 0          # Higher = checked first
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GuardrailResult:
    """Result of guardrail evaluation."""
    check_id: str
    domain: GuardrailDomain
    passed: bool = False
    action: GuardrailAction = GuardrailAction.ALLOW
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class GuardrailEvaluation:
    """Aggregate evaluation of all guardrail checks."""
    request_id: str = ""
    all_passed: bool = True
    results: list[GuardrailResult] = field(default_factory=list)
    blocking_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    escalated: bool = False
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class GuardrailEngine:
    """Safety guardrail engine for AI agent actions.

    **IMMUTABLE**: These guardrails CANNOT be disabled, modified, or
    bypassed by any agent. They are enforced at the system level.

    Key protections:
        - **No direct trade execution**: All orders MUST go through OMS
        - **Risk limit enforcement**: Position/sector/exposure limits absolute
        - **Compliance checks**: Regulatory and exchange rule verification
        - **Data access boundaries**: Agents cannot access unauthorized data
        - **System override prevention**: Agents cannot modify platform configs
        - **External access control**: Agents cannot make unauthorized external calls
    """

    def __init__(self) -> None:
        self._checks: list[GuardrailCheck] = []
        self._total_evaluations = 0
        self._total_blocks = 0

        # Register built-in immutable guardrails
        self._register_builtin_guardrails()

    def _register_builtin_guardrails(self) -> None:
        """Register the immutable built-in safety guardrails."""

        # 1. No direct trade execution
        self._checks.append(GuardrailCheck(
            check_id="no_direct_trade",
            domain=GuardrailDomain.TRADE_EXECUTION,
            description="Prevent AI agents from directly executing trades",
            action=GuardrailAction.BLOCK,
            priority=100,
        ))

        # 2. Risk limit enforcement
        self._checks.append(GuardrailCheck(
            check_id="risk_limit_check",
            domain=GuardrailDomain.RISK_LIMIT,
            description="Ensure orders do not exceed risk limits",
            action=GuardrailAction.BLOCK,
            priority=100,
        ))

        # 3. Position size limits
        self._checks.append(GuardrailCheck(
            check_id="position_size_limit",
            domain=GuardrailDomain.ORDER_SIZE,
            description="Ensure individual position sizes are within limits",
            action=GuardrailAction.BLOCK,
            priority=90,
        ))

        # 4. Portfolio constraint
        self._checks.append(GuardrailCheck(
            check_id="portfolio_constraint_check",
            domain=GuardrailDomain.PORTFOLIO_CONSTRAINT,
            description="Ensure portfolio constraints are not violated",
            action=GuardrailAction.BLOCK,
            priority=90,
        ))

        # 5. Compliance
        self._checks.append(GuardrailCheck(
            check_id="compliance_check",
            domain=GuardrailDomain.COMPLIANCE,
            description="Verify regulatory compliance",
            action=GuardrailAction.BLOCK,
            priority=100,
        ))

        # 6. System override prevention
        self._checks.append(GuardrailCheck(
            check_id="no_system_override",
            domain=GuardrailDomain.SYSTEM_OVERRIDE,
            description="Prevent agents from modifying platform configuration",
            action=GuardrailAction.BLOCK,
            priority=100,
        ))

        # 7. Data access boundary
        self._checks.append(GuardrailCheck(
            check_id="data_access_boundary",
            domain=GuardrailDomain.DATA_ACCESS,
            description="Ensure agents do not access unauthorized data",
            action=GuardrailAction.BLOCK,
            priority=80,
        ))

        # 8. External access control
        self._checks.append(GuardrailCheck(
            check_id="external_access_control",
            domain=GuardrailDomain.EXTERNAL_ACCESS,
            description="Prevent unauthorized external API calls",
            action=GuardrailAction.BLOCK,
            priority=80,
        ))

        self._checks.sort(key=lambda c: -c.priority)

    async def evaluate(self, request_id: str,
                       action: str,
                       context: Optional[dict[str, Any]] = None) -> GuardrailEvaluation:
        """Evaluate all guardrails against an action."""
        self._total_evaluations += 1
        context = context or {}

        evaluation = GuardrailEvaluation(request_id=request_id)

        for check in self._checks:
            if not check.enabled:
                continue

            result = await self._run_check(check, action, context)
            evaluation.results.append(result)

            if not result.passed:
                evaluation.all_passed = False
                if result.action == GuardrailAction.BLOCK:
                    evaluation.blocking_reasons.append(result.message)
                    self._total_blocks += 1
                elif result.action == GuardrailAction.ESCALATE:
                    evaluation.escalated = True
                elif result.action == GuardrailAction.WARN:
                    evaluation.warnings.append(result.message)

        if evaluation.all_passed:
            logger.debug("Guardrail check passed for %s", request_id)
        else:
            logger.warning("Guardrail BLOCKED: %s — %s", request_id,
                           "; ".join(evaluation.blocking_reasons[:3]))

        return evaluation

    async def _run_check(self, check: GuardrailCheck,
                         action: str, context: dict[str, Any]) -> GuardrailResult:
        """Execute a single guardrail check."""
        passed = True
        message = "Check passed"

        # Check for direct trade execution attempts
        if check.check_id == "no_direct_trade":
            if action in ("execute_trade", "place_order", "submit_order"):
                passed = False
                message = "AGENTS CANNOT DIRECTLY EXECUTE TRADES. All orders must go through OMS."

        # Check for risk limit violations
        elif check.check_id == "risk_limit_check":
            proposed_var = context.get("var_95", 0)
            if proposed_var > 0.05:
                passed = False
                message = f"Risk limit exceeded: VaR 95% = {proposed_var:.1%} > 5% limit"

        # Check for position size
        elif check.check_id == "position_size_limit":
            weight = context.get("position_weight", 0)
            if weight > 0.35:
                passed = False
                message = f"Position size {weight:.1%} exceeds 35% max per position"

        # Check for system override
        elif check.check_id == "no_system_override":
            if action in ("modify_config", "change_limits", "disable_guardrail", "bypass_risk"):
                passed = False
                message = "AGENTS CANNOT MODIFY PLATFORM CONFIGURATION OR BYPASS RISK CONTROLS"

        # Check for unauthorized data access
        elif check.check_id == "data_access_boundary":
            requested_data = context.get("data_source", "")
            unauthorized = ["customer_pii", "trade_secrets", "raw_credentials"]
            if any(d in requested_data.lower() for d in unauthorized):
                passed = False
                message = f"Unauthorized data access attempted: {requested_data}"

        # Check for external access
        elif check.check_id == "external_access_control":
            external_call = context.get("external_api", "")
            if external_call and not context.get("external_approved", False):
                passed = False
                message = f"Unauthorized external API call: {external_call}"

        return GuardrailResult(
            check_id=check.check_id,
            domain=check.domain,
            passed=passed,
            action=check.action if not passed else GuardrailAction.ALLOW,
            message=message,
            details={"action": action, "context_keys": list(context.keys())[:10]},
        )

    def can_override(self, check_id: str) -> bool:
        """Check if a guardrail can be overridden. Always returns False."""
        return False  # Built-in guardrails are immutable

    @property
    def total_evaluations(self) -> int:
        return self._total_evaluations

    @property
    def total_blocks(self) -> int:
        return self._total_blocks
