"""
Permission definitions.
"""

from __future__ import annotations

from enum import Enum


class Permission(str, Enum):
    VIEW_POSITION = "VIEW_POSITION"
    CREATE_ORDER = "CREATE_ORDER"
    APPROVE_REPAIR = "APPROVE_REPAIR"
    VIEW_AUDIT = "VIEW_AUDIT"
    ADMIN_CONFIG = "ADMIN_CONFIG"