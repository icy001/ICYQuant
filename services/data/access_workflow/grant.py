"""
Permission grant.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PermissionGrant:
    user: str
    dataset: str
    permission: str