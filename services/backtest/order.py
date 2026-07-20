"""
Virtual order model.
"""

from dataclasses import dataclass


@dataclass
class VirtualOrder:
    id: str
    symbol: str
    side: str
    quantity: float