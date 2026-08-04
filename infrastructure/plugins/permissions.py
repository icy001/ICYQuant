from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from .exceptions import PluginPermissionError


class Permission(Enum):
    READ_CONFIG = "read_config"
    READ_SECRETS = "read_secrets"
    TRADE_ORDER = "trade_order"
    RISK_CONTROL = "risk_control"
    MARKET_DATA = "market_data"
    FILESYSTEM = "filesystem"
    NETWORK = "network"
    DATABASE = "database"
    METRICS = "metrics"
    AUDIT = "audit"
    ADMIN = "admin"


# Permission groups for convenience
DANGEROUS_PERMISSIONS = {Permission.TRADE_ORDER, Permission.RISK_CONTROL, Permission.ADMIN}


@dataclass
class PermissionSet:
    permissions: Set[Permission] = field(default_factory=set)

    def grants(self, perm: Permission) -> bool:
        return perm in self.permissions

    def grant(self, *perms: Permission) -> None:
        for p in perms:
            self.permissions.add(p)

    def revoke(self, *perms: Permission) -> None:
        for p in perms:
            self.permissions.discard(p)

    def to_list(self) -> List[str]:
        return sorted(p.value for p in self.permissions)

    @classmethod
    def from_list(cls, perms: List[str]) -> PermissionSet:
        return cls(permissions={Permission(p) for p in perms})

    def to_dict(self) -> Dict[str, Any]:
        return {"permissions": self.to_list()}


class PermissionChecker:
    """Validates and checks plugin permissions."""

    def __init__(self) -> None:
        self._declared: Dict[str, PermissionSet] = {}

    def declare(self, plugin_id: str, perms: PermissionSet) -> None:
        self._declared[plugin_id] = PermissionSet(permissions=set(perms.permissions))

    def check(self, plugin_id: str, perm: Permission) -> bool:
        perms = self._declared.get(plugin_id)
        if perms is None:
            return False
        return perms.grants(perm)

    def require(self, plugin_id: str, perm: Permission) -> None:
        """Raise PluginPermissionError if the permission is not granted."""
        if not self.check(plugin_id, perm):
            raise PluginPermissionError(plugin_id, perm)

    def audit(self, plugin_id: str) -> Dict[str, Any]:
        perms = self._declared.get(plugin_id)
        if perms is None:
            return {
                "plugin_id": plugin_id,
                "declared": [],
                "dangerous": [],
                "count": 0,
            }
        dangerous = sorted(
            p.value for p in perms.permissions if p in DANGEROUS_PERMISSIONS
        )
        return {
            "plugin_id": plugin_id,
            "declared": perms.to_list(),
            "dangerous": dangerous,
            "count": len(perms.permissions),
        }

    def revoke_all(self, plugin_id: str) -> None:
        self._declared.pop(plugin_id, None)

    def to_dict(self) -> Dict[str, Any]:
        return {pid: perms.to_dict() for pid, perms in self._declared.items()}
