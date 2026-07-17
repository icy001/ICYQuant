"""
Access audit log.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class AccessAudit:
    user: str
    resource: str
    action: str
    result: str