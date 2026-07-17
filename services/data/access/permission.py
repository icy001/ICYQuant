"""
Permission definition.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Permission:
    resource: str
    action: str