"""
Feature definition.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FeatureDefinition:
    name: str
    description: str
    owner: str