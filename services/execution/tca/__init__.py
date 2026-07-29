"""Transaction Cost Analysis (TCA).

Provides post-trade analysis of execution quality:
- Implementation shortfall measurement
- Slippage analysis vs benchmarks
- Cost attribution (spread, impact, delay, commission)
- Execution quality scoring
"""

from .analyzer import TCAAnalyzer, TCAResult
from .benchmark import BenchmarkCalculator, BenchmarkResult

__all__ = [
    "BenchmarkCalculator",
    "BenchmarkResult",
    "TCAAnalyzer",
    "TCAResult",
]
