"""
Alpha factor definition.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AlphaFactor:
    name: str
    category: str
    expression: str
    version: str