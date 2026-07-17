"""
Feature calculation result.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FeatureResult:
    name: str
    value: float
    timestamp: str