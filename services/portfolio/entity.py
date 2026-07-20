"""
Portfolio entity.
"""

from dataclasses import dataclass


@dataclass
class Portfolio:
    portfolio_id: str
    name: str
    status: str