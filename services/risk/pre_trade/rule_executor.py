"""
Rule Executor — Low-level rule execution engine.

Executes individual risk rules with configurable severity handling,
timeout enforcement, and result aggregation. Designed to work with
both built-in and user-defined checkers.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

from .risk_reason import RiskReason, ReasonSeverity, ReasonCategory
from .pre_trade_context import PreTradeContext

logger = logging.getLogger(__name__)


class RuleResult(str, Enum):
    """Result of executing a single rule."""
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"
    SKIP = "SKIP"
    ERROR = "ERROR"
    TIMEOUT = "TIMEOUT"


@dataclass
class RuleExecutionResult:
    """Result of executing a single rule."""
    rule_id: str
    name: str
    result: RuleResult = RuleResult.PASS
    reason: Optional[RiskReason] = None
    duration_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    executed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class RuleExecutor:
    """
    Low-level execution engine for individual risk rules.

    Supports:
    - Pluggable rule functions or callables
    - Severity mapping (WARN vs BLOCK)
    - Timeout enforcement per rule
    - Result aggregation into PreTradeContext.

    Usage::

        executor = RuleExecutor()
        result = await executor.execute_rule(
            rule_id="RL-001",
            name="Position Check",
            rule_fn=my_checker.check,
            ctx=context,
            severity=ReasonSeverity.BLOCKING,
            timeout=2.0,
        )
    """

    def __init__(self) -> None:
        self._stats: dict[str, int] = {
            "total_executions": 0,
            "passed": 0,
            "failed": 0,
            "warned": 0,
            "timeouts": 0,
            "errors": 0,
        }

    async def execute_rule(
        self,
        rule_id: str,
        name: str,
        rule_fn: Callable,
        ctx: PreTradeContext,
        severity: ReasonSeverity = ReasonSeverity.BLOCKING,
        category: Optional[ReasonCategory] = None,
        timeout: float = 3.0,
        metadata: Optional[dict[str, Any]] = None,
    ) -> RuleExecutionResult:
        """
        Execute a single risk rule with timeout enforcement.

        Args:
            rule_id: Unique rule identifier.
            name: Human-readable rule name.
            rule_fn: Async callable that takes ctx and returns (passed: bool, message: str).
            ctx: Pre-trade evaluation context.
            severity: Reason severity if the rule fails/warns.
            category: Reason category for failures.
            timeout: Maximum execution time in seconds.
            metadata: Additional metadata for the execution result.

        Returns:
            RuleExecutionResult with PASS/FAIL/WARN/TIMEOUT/ERROR.
        """
        self._stats["total_executions"] += 1
        t_start = datetime.now(timezone.utc)

        try:
            result_tuple = await asyncio.wait_for(
                rule_fn(ctx), timeout=timeout
            )
        except asyncio.TimeoutError:
            self._stats["timeouts"] += 1
            duration_ms = (datetime.now(timezone.utc) - t_start).total_seconds() * 1000
            reason = RiskReason.blocking(
                category=category or ReasonCategory.GENERAL,
                message=f"Rule `{name}` timed out after {timeout}s.",
                checker=name,
                rule_id=rule_id,
            )
            ctx.add_reason(reason)
            ctx.add_checker_result(name, passed=False, rule_id=rule_id)
            return RuleExecutionResult(
                rule_id=rule_id,
                name=name,
                result=RuleResult.TIMEOUT,
                reason=reason,
                duration_ms=duration_ms,
                metadata=metadata or {},
            )
        except Exception as e:
            self._stats["errors"] += 1
            duration_ms = (datetime.now(timezone.utc) - t_start).total_seconds() * 1000
            reason = RiskReason.blocking(
                category=category or ReasonCategory.GENERAL,
                message=f"Rule `{name}` error: {str(e)}",
                checker=name,
                rule_id=rule_id,
            )
            ctx.add_reason(reason)
            ctx.add_checker_result(name, passed=False, rule_id=rule_id)
            return RuleExecutionResult(
                rule_id=rule_id,
                name=name,
                result=RuleResult.ERROR,
                reason=reason,
                duration_ms=duration_ms,
                metadata=metadata or {},
            )

        # Parse result
        duration_ms = (datetime.now(timezone.utc) - t_start).total_seconds() * 1000
        passed, message = self._parse_result(result_tuple)

        if passed:
            self._stats["passed"] += 1
            ctx.add_checker_result(name, passed=True, rule_id=rule_id)
            return RuleExecutionResult(
                rule_id=rule_id,
                name=name,
                result=RuleResult.PASS,
                duration_ms=duration_ms,
                metadata=metadata or {},
            )

        # Determine if this is a WARN or FAIL
        is_warning = severity == ReasonSeverity.WARNING
        if is_warning:
            self._stats["warned"] += 1
            reason = RiskReason.warning(
                category=category or ReasonCategory.GENERAL,
                message=message or f"Rule `{name}` warning.",
                checker=name,
                rule_id=rule_id,
            )
            ctx.add_reason(reason)
            ctx.add_checker_result(name, passed=True, rule_id=rule_id)
            return RuleExecutionResult(
                rule_id=rule_id,
                name=name,
                result=RuleResult.WARN,
                reason=reason,
                duration_ms=duration_ms,
                metadata=metadata or {},
            )

        self._stats["failed"] += 1
        reason = RiskReason.blocking(
            category=category or ReasonCategory.GENERAL,
            message=message or f"Rule `{name}` failed.",
            checker=name,
            rule_id=rule_id,
        )
        ctx.add_reason(reason)
        ctx.add_checker_result(name, passed=False, rule_id=rule_id)
        return RuleExecutionResult(
            rule_id=rule_id,
            name=name,
            result=RuleResult.FAIL,
            reason=reason,
            duration_ms=duration_ms,
            metadata=metadata or {},
        )

    def get_stats(self) -> dict[str, int]:
        return dict(self._stats)

    @staticmethod
    def _parse_result(result: Any) -> tuple[bool, str]:
        """Parse the result from a rule function into (passed, message)."""
        if isinstance(result, bool):
            return (result, "")
        if isinstance(result, tuple) and len(result) == 2:
            return result[0], str(result[1])
        if isinstance(result, dict):
            return result.get("passed", False), result.get("message", "")
        return (bool(result), "")
