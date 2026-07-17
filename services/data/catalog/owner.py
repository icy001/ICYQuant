"""
Dataset ownership.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class DataOwner:
    team: str
    contact: str