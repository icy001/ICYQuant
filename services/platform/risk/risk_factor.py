"""
Risk factor model.
"""

from dataclasses import dataclass


@dataclass
class RiskFactor:

    name: str

    exposure: float

    contribution: float