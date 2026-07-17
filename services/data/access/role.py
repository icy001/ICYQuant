"""
User role.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Role:
    name: str