"""
Monte Carlo simulation result.
"""

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class MonteCarloResult:

    iterations: int

    mean_return: float

    confidence_interval: Tuple[float, float]