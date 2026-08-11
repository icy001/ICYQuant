"""
Risk Policy — Unified risk policy rules definition.

Defines position limits, loss limits, exposure limits, leverage limits,
and compliance rules as standardized policy objects.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class PolicyType(str, Enum):
    """Types of risk policies."""
    POSITION_LIMIT = "position_limit"
    LOSS_LIMIT = "loss_limit"
    EXPOSURE_LIMIT = "exposure_limit"
    LEVERAGE_LIMIT = "leverage_limit"
    COMPLIANCE_RULE = "compliance_rule"
    CONCENTRATION_LIMIT = "concentration_limit"
    LIQUIDITY_CONSTRAINT = "liquidity_constraint"
    VOLATILITY_CONSTRAINT = "volatility_constraint"
    CUSTOM = "custom"


class PolicySeverity(str, Enum):
    """Policy severity levels."""
    BLOCKING = "blocking"  # Rejects the order
    WARNING = "warning"    # Allows but warns
    ESCALATE = "escalate"  # Requires manual review


@dataclass
class RiskPolicy:
    """Definition of a risk policy rule."""
    policy_id: str
    name: str
    policy_type: PolicyType
    severity: PolicySeverity = PolicySeverity.BLOCKING
    description: str = ""
    threshold: float = 0.0
    limit_value: float = 0.0
    enabled: bool = True
    priority: int = 0
    condition: Optional[Callable] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class PolicyEvaluationResult:
    """Result of evaluating a single policy."""
    policy_id: str
    policy_name: str
    policy_type: PolicyType
    passed: bool
    current_value: float = 0.0
    limit_value: float = 0.0
    severity: PolicySeverity = PolicySeverity.BLOCKING
    message: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class RiskPolicyEngine:
    """
    Unified risk policy rules engine.

    Manages and evaluates position limits, loss limits, exposure limits,
    leverage limits, and compliance rules as configurable policy objects.

    Usage::

        engine = RiskPolicyEngine()
        await engine.initialize()
        policy = await engine.register(RiskPolicy(
            policy_id="max_position_AAPL",
            name="AAPL Position Limit",
            policy_type=PolicyType.POSITION_LIMIT,
            threshold=10000,
            severity=PolicySeverity.BLOCKING,
        ))
        result = await engine.evaluate("max_position_AAPL", current_value=5000)
    """

    def __init__(self) -> None:
        self._policies: dict[str, RiskPolicy] = {}
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the policy engine."""
        logger.info("RiskPolicyEngine initialized.")

    async def stop(self) -> None:
        """Stop the policy engine."""
        logger.info("RiskPolicyEngine stopped.")

    # ---- Policy Management ----

    async def register(self, policy: RiskPolicy) -> RiskPolicy:
        """Register a risk policy."""
        async with self._lock:
            self._policies[policy.policy_id] = policy
        logger.info(f"Risk policy registered: {policy.policy_id} ({policy.policy_type.value})")
        return policy

    async def update(self, policy_id: str, **kwargs: Any) -> Optional[RiskPolicy]:
        """Update a risk policy."""
        async with self._lock:
            policy = self._policies.get(policy_id)
            if not policy:
                return None
            for key, value in kwargs.items():
                if hasattr(policy, key):
                    setattr(policy, key, value)
            policy.updated_at = datetime.now(timezone.utc)
        return policy

    async def remove(self, policy_id: str) -> bool:
        """Remove a risk policy."""
        async with self._lock:
            if policy_id in self._policies:
                del self._policies[policy_id]
                return True
            return False

    async def get(self, policy_id: str) -> Optional[RiskPolicy]:
        """Get a policy by ID."""
        return self._policies.get(policy_id)

    # ---- Evaluation ----

    async def evaluate(
        self,
        policy_id: str,
        current_value: float,
    ) -> PolicyEvaluationResult:
        """Evaluate a policy against a current value."""
        policy = self._policies.get(policy_id)
        if not policy:
            return PolicyEvaluationResult(
                policy_id=policy_id,
                policy_name="unknown",
                policy_type=PolicyType.CUSTOM,
                passed=True,
                current_value=current_value,
                message=f"Policy not found: {policy_id}",
            )

        passed = current_value <= policy.threshold if policy.threshold > 0 else True

        return PolicyEvaluationResult(
            policy_id=policy_id,
            policy_name=policy.name,
            policy_type=policy.policy_type,
            passed=passed,
            current_value=current_value,
            limit_value=policy.threshold,
            severity=policy.severity,
            message="Within limit" if passed else f"Exceeds limit of {policy.threshold}",
        )

    async def evaluate_all(
        self,
        current_values: dict[str, float],
    ) -> list[PolicyEvaluationResult]:
        """Evaluate all enabled policies."""
        results = []
        for policy_id, policy in self._policies.items():
            if not policy.enabled:
                continue
            current = current_values.get(policy_id, 0.0)
            result = await self.evaluate(policy_id, current)
            results.append(result)
        return results

    # ---- Bulk Operations ----

    async def enable(self, policy_id: str) -> Optional[RiskPolicy]:
        """Enable a policy."""
        return await self.update(policy_id, enabled=True)

    async def disable(self, policy_id: str) -> Optional[RiskPolicy]:
        """Disable a policy."""
        return await self.update(policy_id, enabled=False)

    async def list_active(self) -> list[RiskPolicy]:
        """List all enabled policies, ordered by priority."""
        active = [p for p in self._policies.values() if p.enabled]
        return sorted(active, key=lambda p: p.priority, reverse=True)

    async def list_by_type(self, policy_type: PolicyType) -> list[RiskPolicy]:
        """List policies by type."""
        return [p for p in self._policies.values() if p.policy_type == policy_type]

    async def health_check(self) -> dict[str, Any]:
        """Check policy engine health."""
        return {
            "status": "healthy",
            "total_policies": len(self._policies),
            "active_policies": len([p for p in self._policies.values() if p.enabled]),
        }
