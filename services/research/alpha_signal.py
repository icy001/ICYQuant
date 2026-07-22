"""
Alpha signal.
"""

from dataclasses import dataclass


@dataclass
class AlphaSignal:

    alpha_id: str

    symbol: str

    score: float

    timestamp: str