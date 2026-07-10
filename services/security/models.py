"""
Security domain models.
"""

from __future__ import annotations

from dataclasses import dataclass

from enum import Enum


class Role(str, Enum):
    TRADER = "TRADER"
    RISK_MANAGER = "RISK_MANAGER"
    ADMIN = "ADMIN"
    AUDITOR = "AUDITOR"


@dataclass(
    frozen=True,
)
class User:
    __slots__ = (
        "user_id",
        "username",
        "role",
    )
    user_id: str
    username: str
    role: Role