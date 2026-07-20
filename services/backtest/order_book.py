"""
Virtual order book.
"""

from dataclasses import dataclass, field


@dataclass
class VirtualOrderBook:
    bids: list = field(default_factory=list)
    asks: list = field(default_factory=list)