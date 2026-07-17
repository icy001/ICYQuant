"""
Dataset subscription.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class DatasetSubscription:
    user: str
    dataset: str
    status: str = "ACTIVE"