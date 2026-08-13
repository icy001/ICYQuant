"""Commit 28 Part 1.4 — Authority Model, Resolution and Boundary.

The Part 1.4 problem statement:

    "有资格批准" != "现在有权批准"
    (being *eligible* to approve != *currently having* the authority)

This module separates three concepts:

    Role Authority      — what a role grants ("你能做什么")
    Delegated Authority — a scoped, time-bound slice granted by another
                          principal
    Authority Boundary  — authority alone never authorizes execution;
                          Policy + Context are still required

Pipeline:

    Principal
      ├── Role Authority
      └── Delegated Authority
                    │
                    ▼
              Authority Resolver
                    │
                    ▼
               Policy Engine
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Iterable, Optional

if TYPE_CHECKING:
    from .delegation import AuthorityDelegation, ScopedDelegationValidator
    from .registry import GovernanceRegistry


class AuthoritySource(str, Enum):
    """Where an :class:`Authority` comes from."""

    ROLE = "ROLE"
    DELEGATION = "DELEGATION"
    EMERGENCY = "EMERGENCY"


@dataclass(frozen=True)
class Authority:
    """A single grant of authority for a resource and a set of actions."""

    principal_id: str
    resource: str
    actions: tuple[str, ...]
    source: str
    source_id: str | None = None

    def allows(self, resource: str, action: str) -> bool:
        """True when this authority covers exactly resource+action."""
        return self.resource == resource and action in self.actions


@dataclass(frozen=True)
class RolePermissionView:
    """Adapter fed to :class:`AuthorityResolver` for ROLE-sourced authority.

    Exposes the ``role_id`` and the ``(resource, action)`` permission pairs
    of a role, so the resolver never has to know about the registry.
    """

    role_id: str
    permissions: frozenset[tuple[str, str]] = frozenset()


class AuthorityResolver:
    """Resolves the current effective authority for a principal.

    Sources, in order:
      1. ROLE      — from the principal's roles' permission pairs;
      2. DELEGATION — from every delegation that is currently valid
         (enabled + principal + resource + action + time window).

    Returned authorities carry their ``source`` / ``source_id`` so the
    audit trail can explain *why* a principal was authorized.
    """

    def __init__(
        self,
        delegations: Iterable["AuthorityDelegation"] = (),
        validator: Optional["ScopedDelegationValidator"] = None,
    ) -> None:
        self._delegations = tuple(delegations or ())
        if validator is None:
            from .delegation import ScopedDelegationValidator

            validator = ScopedDelegationValidator()
        self._validator = validator

    def resolve(
        self,
        principal_id: str,
        resource: str,
        action: str,
        roles: Iterable = (),
        delegations: Optional[Iterable["AuthorityDelegation"]] = None,
        now: Optional[datetime] = None,
    ) -> tuple[Authority, ...]:
        """Resolve all authorities covering ``resource+action``.

        ``roles`` is an iterable of objects exposing ``role_id`` and
        ``permissions`` (a collection of ``(resource, action)`` pairs),
        e.g. :class:`RolePermissionView`.
        """
        authorities = []

        for role in roles:
            permissions = getattr(role, "permissions", ()) or ()
            if (resource, action) in permissions:
                authorities.append(
                    Authority(
                        principal_id=principal_id,
                        resource=resource,
                        actions=(action,),
                        source=AuthoritySource.ROLE,
                        source_id=role.role_id,
                    )
                )

        for delegation in delegations if delegations is not None else self._delegations:
            if self._validator.is_valid(
                delegation, principal_id, resource, action, now
            ):
                authorities.append(
                    Authority(
                        principal_id=principal_id,
                        resource=resource,
                        actions=(action,),
                        source=AuthoritySource.DELEGATION,
                        source_id=delegation.delegation_id,
                    )
                )

        return tuple(authorities)

    @classmethod
    def resolve_from_registry(
        cls,
        principal_id: str,
        resource: str,
        action: str,
        registry: "GovernanceRegistry",
        role_ids: Iterable[str] = (),
        delegations: Iterable["AuthorityDelegation"] = (),
        now: Optional[datetime] = None,
    ) -> tuple[Authority, ...]:
        """Convenience: build role permission views straight from a
        :class:`GovernanceRegistry` and resolve authority."""
        resolver = cls(delegations=delegations)
        views = []
        for role_id in role_ids:
            role = registry.get_role(role_id)
            if role is None:
                continue
            pairs = set()
            for permission_id in registry.permissions_for_role(role_id):
                permission = registry.get_permission(permission_id)
                if permission is not None:
                    pairs.add((permission.resource, permission.action))
            views.append(
                RolePermissionView(
                    role_id=role.role_id, permissions=frozenset(pairs)
                )
            )
        return resolver.resolve(principal_id, resource, action, views, now=now)


@dataclass(frozen=True)
class AuthoritySnapshot:
    """Audit snapshot of the authority an approver held at approval time.

    Recorded when an approval happens:

        APR-001
        approver : risk-001
        roles    : (RISK_OPERATOR,)
        authority: trading:kill
        policy   : POLICY-KILL-001

    A snapshot is for AUDIT ONLY: it never grants current authority.
    Execution always re-evaluates current governance + current authority
    + a still-valid approval (Snapshot != Current Authority).
    """

    approval_id: str
    approver_id: str
    roles: tuple[str, ...]
    resource: str
    action: str
    policy_id: str | None = None
    source: str = "ROLE"
    source_id: str | None = None
    captured_at: datetime | None = None
