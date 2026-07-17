"""
Feature value.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Feature:
    symbol: str
    name: str
    value: float
    timestamp: datetime