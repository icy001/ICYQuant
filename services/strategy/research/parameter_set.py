"""
Strategy parameters.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ParameterSet:
    name: str
    values: dict