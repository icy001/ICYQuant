"""
Dataset sharing request.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SharingRequest:
    owner: str
    receiver: str
    dataset: str
    status: str = "PENDING"