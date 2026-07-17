"""
Alert definition.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Alert:
    level: str
    message: str