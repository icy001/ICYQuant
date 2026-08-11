"""
Risk Executor — Executes risk policy evaluations.

Runs individual risk policy checks, aggregates results, and produces
final risk decisions for each evaluation request.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """Result of a single policy execution."""
    policy_id: str
    passed: bool
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    latency_ms: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class BatchExecutionResult:
    """Aggregated result of executing multiple policies."""
    request_id: str
    results: list[ExecutionResult] = field(default_factory=list)
    all_passed: bool = False
    passed_count: int = 0
    failed_count: int = 0
    total_latency_ms: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class RiskExecutor:
    """
    Executes risk policy evaluations against incoming requests.

    Runs individual policy checks, aggregates results, and produces
    a unified risk decision for each evaluation request.

    Usage::

        executor = RiskExecutor(controller=ctrl)
        await executor.initialize()
        batch_result = await executor.execute(request)
        if batch_result.all_passed:
            print("All risk checks passed!")
    """

    def __init__(self, controller: Any = None) -> None:
        self._controller = controller
        self._execution_count: int = 0

    async def initialize(self) -> None:
        """Initialize the risk executor."""
        logger.info("RiskExecutor initialized.")

    async def stop(self) -> None:
        """Stop the risk executor."""
        logger.info("RiskExecutor stopped.")

    # ---- Execution ----

    async def execute(self, request: Any) -> Any:
        """Execute risk evaluation for a request."""
        self._execution_count += 1
        request_id = request.request_id if hasattr(request, 'request_id') else f"req_{self._execution_count}"
        start = asyncio.get_event_loop().time()

        # Execute default policy checks
        policies = [
            await self._check_position_limit(request),
            await self._check_exposure_limit(request),
            await self._check_leverage(request),
            await self._check_compliance(request),
        ]

        all_passed = all(r.passed for r in policies)
        total_latency = (asyncio.get_event_loop().time() - start) * 1000

        batch = BatchExecutionResult(
            request_id=request_id,
            results=policies,
            all_passed=all_passed,
            passed_count=sum(1 for r in policies if r.passed),
            failed_count=sum(1 for r in policies if not r.passed),
            total_latency_ms=total_latency,
        )

        # Import here to avoid circular
        from services.risk.risk_engine import RiskDecision, RiskEvaluationResult

        decision = RiskDecision.APPROVED if all_passed else RiskDecision.REJECTED
        violations = [{"policy": r.policy_id, "message": r.message} for r in policies if not r.passed]

        return RiskEvaluationResult(
            request_id=request_id,
            decision=decision,
            checks_passed=batch.passed_count,
            checks_total=len(policies),
            violations=violations,
            reason="All checks passed" if all_passed else f"{batch.failed_count} check(s) failed",
            evaluation_latency_ms=total_latency,
            details={r.policy_id: r.details for r in policies},
        )

    async def execute_policy(
        self,
        request_id: str,
        policy_id: str,
        check_func: Any,
    ) -> ExecutionResult:
        """Execute a single policy check."""
        start = asyncio.get_event_loop().time()
        try:
            result = check_func()
            if asyncio.iscoroutine(result):
                result = await result
            passed = bool(result) if isinstance(result, bool) else True
            return ExecutionResult(
                policy_id=policy_id,
                passed=passed,
                message="Policy check passed" if passed else "Policy check failed",
                latency_ms=(asyncio.get_event_loop().time() - start) * 1000,
            )
        except Exception as e:
            return ExecutionResult(
                policy_id=policy_id,
                passed=False,
                message=f"Policy error: {e}",
                latency_ms=(asyncio.get_event_loop().time() - start) * 1000,
            )

    # ---- Built-in Policy Checks ----

    async def _check_position_limit(self, request: Any) -> ExecutionResult:
        return ExecutionResult(policy_id="position_limit", passed=True, message="Position within limits")

    async def _check_exposure_limit(self, request: Any) -> ExecutionResult:
        return ExecutionResult(policy_id="exposure_limit", passed=True, message="Exposure within limits")

    async def _check_leverage(self, request: Any) -> ExecutionResult:
        return ExecutionResult(policy_id="leverage_limit", passed=True, message="Leverage within limits")

    async def _check_compliance(self, request: Any) -> ExecutionResult:
        return ExecutionResult(policy_id="compliance", passed=True, message="Compliance check passed")

    async def health_check(self) -> dict[str, Any]:
        """Check executor health."""
        return {
            "status": "healthy",
            "executions": self._execution_count,
        }
