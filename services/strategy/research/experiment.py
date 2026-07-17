"""
Strategy research experiment.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Experiment:
    experiment_id: str
    strategy_id: str
    version: str
    description: str