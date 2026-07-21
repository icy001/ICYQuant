"""
Audit action types.
"""

from enum import Enum


class AuditType(Enum):

    CREATE = "CREATE"

    UPDATE = "UPDATE"

    DELETE = "DELETE"

    REBALANCE = "REBALANCE"

    CONFIG_CHANGE = "CONFIG_CHANGE"