"""
Portfolio model.
"""

from dataclasses import dataclass, field


@dataclass
class Portfolio:
    cash: float
    equity: float
    positions: dict = field(default_factory=dict)