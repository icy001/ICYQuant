"""
Lifecycle operation result.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class LifecycleResult:
    success: bool
    new_state: str
    reason: str