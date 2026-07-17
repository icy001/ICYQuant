"""
Approval decision.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Approval:
    approver: str
    decision: str