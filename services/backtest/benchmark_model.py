"""
Benchmark model.
"""

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class Benchmark:
    name: str
    returns: List[float]