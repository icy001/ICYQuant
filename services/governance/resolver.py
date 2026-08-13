"""Commit 28 Part 1.2 — Permission Resolver.

Answers "does any of these roles hold the resource:action permission?".
Permission is Capability; Policy is Constraint. The resolver only
answers the capability question.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .registry import GovernanceRegistry


class PermissionResolver:
    """Resolves whether a set of role ids holds a resource:action permission.

    Backed by a GovernanceRegistry: the role -> permission mapping is
    read from ``permissions_for_role``, which itself uses the standard
    role/permission table registered at build time.
    """

    def __init__(self, registry: GovernanceRegistry) -> None:
        self._registry = registry

    @property
    def registry(self) -> GovernanceRegistry:
        return self._registry

    def has_permission(self, role_ids, resource: str, action: str) -> bool:
        target = f"{resource}:{action}"

        for role_id in role_ids:
            for permission_id in self._registry.permissions_for_role(role_id):
                if permission_id == target:
                    return True

        return False
