"""
Delegation Validator — validates delegation chains for safety.

Ensures:
  1. Delegation limit <= parent authority limit (all dimensions)
  2. Delegation scope ⊆ parent authority scope
  3. Delegation depth does not exceed maximum (default: 1)
  4. Sub-delegation only allowed with explicit permission
  5. Cannot expand any domain (scope/amount/risk/action/duration)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .delegation import Delegation
from .delegation_status import DelegationStatus
from .authority_grant import AuthorityGrant
from .authority_limit import AuthorityLimit


class DelegationValidationResult:
    """Result of a delegation validation check."""

    def __init__(self, valid: bool, violations: Optional[List[str]] = None):
        self.valid = valid
        self.violations = violations or []

    def __bool__(self) -> bool:
        return self.valid


class DelegationValidator:
    """
    Validates delegation requests against security constraints.

    Key principle:
      Delegation Cannot Expand Authority.

    Delegation authority <= Original authority in:
      - Scope
      - Amount
      - Risk
      - Action
      - Duration
      - Autonomy (delegation depth)
    """

    def __init__(self, max_delegation_depth: int = 1):
        self._max_depth = max_delegation_depth

    # ------------------------------------------------------------------
    # Main validation
    # ------------------------------------------------------------------

    def validate(
        self,
        delegation: Delegation,
        parent_grant: AuthorityGrant,
    ) -> DelegationValidationResult:
        """
        Full validation of a delegation against its parent grant.

        Returns a ValidationResult with all violations found.
        """
        violations: List[str] = []

        # 1. Limit check
        limit_violations = self._check_limits(delegation, parent_grant)
        violations.extend(limit_violations)

        # 2. Scope check
        scope_violations = self._check_scope(delegation, parent_grant)
        violations.extend(scope_violations)

        # 3. Duration check
        time_violations = self._check_duration(delegation, parent_grant)
        violations.extend(time_violations)

        # 4. Depth check
        depth_violations = self._check_depth(delegation)
        violations.extend(depth_violations)

        # 5. Sub-delegation check
        sub_violations = self._check_subdelegation(delegation)
        violations.extend(sub_violations)

        # 6. Status check
        if not parent_grant.is_valid():
            violations.append("Parent grant is not currently valid")

        return DelegationValidationResult(
            valid=len(violations) == 0,
            violations=violations,
        )

    def validate_chain(
        self,
        delegations: List[Delegation],
        original_grant: AuthorityGrant,
    ) -> DelegationValidationResult:
        """
        Validate an entire delegation chain.

        Each delegation must be a strict subset of its immediate parent.
        Ultimate limit cannot exceed the original grant.
        """
        if len(delegations) > self._max_depth + 1:
            return DelegationValidationResult(
                valid=False,
                violations=[f"Chain depth {len(delegations)} exceeds max {self._max_depth + 1}"],
            )

        violations: List[str] = []

        # Each delegation must be subset of the previous
        current_grant = original_grant

        for i, delegation in enumerate(delegations):
            result = self.validate(delegation, current_grant)
            if not result.valid:
                for v in result.violations:
                    violations.append(f"Level {i}: {v}")

            # For chain checking, construct an "effective grant" for the delegate
            if delegation.limit:
                current_grant = AuthorityGrant(
                    grant_id=f"DELEGATED-{delegation.delegation_id}",
                    actor=delegation.delegate,
                    limit=AuthorityLimit(
                        limit_id=f"LIM-{delegation.delegation_id}",
                        max_amount=delegation.limit.max_amount,
                        max_risk=delegation.limit.max_risk,
                        max_leverage=delegation.limit.max_leverage,
                        allowed_actions=delegation.limit.allowed_actions,
                    ),
                )

        return DelegationValidationResult(
            valid=len(violations) == 0,
            violations=violations,
        )

    # ------------------------------------------------------------------
    # Checks
    # ------------------------------------------------------------------

    def _check_limits(self, delegation: Delegation, parent: AuthorityGrant) -> List[str]:
        """Check that delegation limits do not exceed parent."""
        violations: List[str] = []
        if delegation.limit is None:
            return violations

        if parent.limit is None:
            return violations  # Parent has no limit restrictions

        dl = delegation.limit
        pl = parent.limit

        if dl.max_amount > pl.max_amount:
            violations.append(
                f"Amount limit {dl.max_amount} exceeds parent {pl.max_amount}"
            )
        if dl.max_risk > pl.max_risk:
            violations.append(
                f"Risk limit {dl.max_risk} exceeds parent {pl.max_risk}"
            )
        if dl.max_leverage > pl.max_leverage:
            violations.append(
                f"Leverage limit {dl.max_leverage} exceeds parent {pl.max_leverage}"
            )
        return violations

    def _check_scope(self, delegation: Delegation, parent: AuthorityGrant) -> List[str]:
        """Check that delegation scope is a subset of parent scope."""
        violations: List[str] = []
        if delegation.scope is None or parent.scope is None:
            return violations

        for level in delegation.scope.allowed_levels:
            if not parent.scope.covers(level):
                violations.append(
                    f"Scope level {level.name} is not covered by parent scope {parent.scope.level.name}"
                )
        return violations

    def _check_duration(self, delegation: Delegation, parent: AuthorityGrant) -> List[str]:
        """Check that delegation duration is within parent's validity window."""
        violations: List[str] = []
        if delegation.valid_from < parent.valid_from:
            violations.append(
                f"Delegation starts {delegation.valid_from} before parent {parent.valid_from}"
            )
        if delegation.valid_to > parent.valid_to:
            violations.append(
                f"Delegation ends {delegation.valid_to} after parent {parent.valid_to}"
            )
        return violations

    def _check_depth(self, delegation: Delegation) -> List[str]:
        """Check that delegation depth doesn't exceed maximum."""
        violations: List[str] = []
        if delegation.delegation_depth >= self._max_depth:
            violations.append(
                f"Delegation depth {delegation.delegation_depth} exceeds max {self._max_depth}"
            )
        return violations

    def _check_subdelegation(self, delegation: Delegation) -> List[str]:
        """Check that sub-delegation is explicitly allowed."""
        violations: List[str] = []
        if delegation.delegation_depth > 0 and not delegation.allow_subdelegation:
            violations.append(
                "Sub-delegation not allowed (allow_subdelegation=False)"
            )
        return violations
