"""
Access request model.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class AccessRequest:
    user: str
    dataset: str
    reason: str
    status: str = "REQUESTED"