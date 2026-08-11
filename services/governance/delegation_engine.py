"""
Delegation Engine — processes delegations and manages their lifecycle.

The Delegation Engine:
  1. Validates delegation requests against parent authority
  2. Tracks active delegations
  3. Handles expiry and revocation
  4. Prevents delegation chain abuse (max depth enforcement)
  5. Ensures delegation cannot expand original authority
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

from .delegation import Delegation
from .delegation_status import DelegationStatus
from .delegation_validator import DelegationValidator, DelegationValidationResult
from .authority_grant import AuthorityGrant


class DelegationEngine:
    """
    Manages the lifecycle of authority delegations.

    Core responsibility: ensure that delegations are safe, scoped,
    and cannot be used to expand authority beyond original limits.
    """

    def __init__(self, max_delegation_depth: int = 1):
        self._validator = DelegationValidator(max_delegation_depth=max_delegation_depth)
        self._delegations: Dict[str, Delegation] = {}
        self._by_delegator: Dict[str, List[str]] = {}
        self._by_delegate: Dict[str, List[str]] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_delegation(
        self,
        delegation: Delegation,
        parent_grant: AuthorityGrant,
    ) -> DelegationValidationResult:
        """
        Validate and register a delegation.

        Delegation is registered regardless of validation result,
        but only ACTIVE-status delegations are used at runtime.
        Invalid delegations are recorded as INVALID for audit.
        """
        result = self._validator.validate(delegation, parent_grant)

        if result.valid:
            delegation.activate()
        else:
            delegation.status = DelegationStatus.INVALID

        self._store(delegation)
        return result

    def create_delegation(
        self,
        delegator: str,
        delegate: str,
        parent_grant: AuthorityGrant,
        max_amount: float = float("inf"),
        max_risk: float = float("inf"),
        reason: str = "",
        valid_from: float = 0.0,
        valid_to: float = float("inf"),
        allow_subdelegation: bool = False,
    ) -> Tuple[Delegation, DelegationValidationResult]:
        """
        Create and register a delegation in one step.

        Returns (delegation, validation_result).
        """
        from .delegation_scope import DelegationScope
        from .delegation_limit import DelegationLimit

        now = time.time()
        if valid_from <= 0:
            valid_from = now

        # Scope — copy from parent
        scope = None
        if parent_grant.scope:
            scope = DelegationScope(
                scope_id=f"DS-{delegate}",
                allowed_levels=parent_grant.scope.allowed_levels,
                portfolio_ids=parent_grant.scope.portfolio_ids,
                strategy_ids=parent_grant.scope.strategy_ids,
            )

        # Limit — cap at parent's limits
        parent_max_amt = parent_grant.limit.max_amount if parent_grant.limit else float("inf")
        parent_max_risk = parent_grant.limit.max_risk if parent_grant.limit else float("inf")
        parent_max_lev = parent_grant.limit.max_leverage if parent_grant.limit else float("inf")

        limit = DelegationLimit(
            limit_id=f"DL-{delegate}",
            max_amount=min(max_amount, parent_max_amt),
            max_risk=min(max_risk, parent_max_risk),
            max_leverage=min(float("inf"), parent_max_lev),
            allowed_actions=parent_grant.limit.allowed_actions if parent_grant.limit else [],
            valid_from=valid_from,
            valid_to=min(valid_to, parent_grant.valid_to),
        )

        delegation = Delegation.create(
            delegator=delegator,
            delegate=delegate,
            parent_grant=parent_grant,
            scope=scope,
            limit=limit,
            reason=reason,
            valid_from=valid_from,
            valid_to=valid_to,
            allow_subdelegation=allow_subdelegation,
        )

        result = self.register_delegation(delegation, parent_grant)
        return delegation, result

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_delegation(self, delegation_id: str) -> Optional[Delegation]:
        """Get a delegation by ID."""
        return self._delegations.get(delegation_id)

    def get_active_delegation(self, delegator: str, delegate: str) -> Optional[Delegation]:
        """Get an active delegation between specific parties."""
        for del_id in self._by_delegator.get(delegator, []):
            d = self._delegations.get(del_id)
            if d and d.delegate == delegate and d.is_active():
                return d
        return None

    def get_delegations_for_delegator(self, delegator: str) -> List[Delegation]:
        """Get all delegations made by a delegator."""
        ids = self._by_delegator.get(delegator, [])
        return [self._delegations[i] for i in ids if i in self._delegations]

    def get_delegations_for_delegate(self, delegate: str) -> List[Delegation]:
        """Get all delegations where someone is the delegate."""
        ids = self._by_delegate.get(delegate, [])
        return [self._delegations[i] for i in ids if i in self._delegations]

    def get_active_delegations(self) -> List[Delegation]:
        """Get all currently active delegations."""
        return [d for d in self._delegations.values() if d.is_active()]

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def revoke_delegation(self, delegation_id: str, actor: str = "SYSTEM", reason: str = "") -> bool:
        """Revoke an active delegation."""
        delegation = self._delegations.get(delegation_id)
        if delegation is None:
            return False
        if not delegation.is_active():
            return False
        delegation.revoke(actor, reason)
        return True

    def expire_delegation(self, delegation_id: str) -> bool:
        """Mark a delegation as expired."""
        delegation = self._delegations.get(delegation_id)
        if delegation is None:
            return False
        delegation.expire()
        return True

    def expire_overdue(self) -> int:
        """Expire all overdue delegations. Returns count."""
        count = 0
        for d in self._delegations.values():
            if d.status == DelegationStatus.ACTIVE and not d.is_active():
                d.expire()
                count += 1
        return count

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def count_active(self) -> int:
        """Count active delegations."""
        return len(self.get_active_delegations())

    def count_total(self) -> int:
        """Total delegations registered."""
        return len(self._delegations)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _store(self, delegation: Delegation) -> None:
        """Store a delegation in the registry."""
        self._delegations[delegation.delegation_id] = delegation

        if delegation.delegator not in self._by_delegator:
            self._by_delegator[delegation.delegator] = []
        self._by_delegator[delegation.delegator].append(delegation.delegation_id)

        if delegation.delegate not in self._by_delegate:
            self._by_delegate[delegation.delegate] = []
        self._by_delegate[delegation.delegate].append(delegation.delegation_id)
