"""Execution Optimization Engine.

Provides intelligent order execution through:
- Smart order slicing (TWAP, VWAP, POV)
- Market impact estimation
- Algorithm selection and optimization
- Execution plan generation
"""

from .algorithms import AdaptiveExecutor, PovExecutor, TwapExecutor, VwapExecutor
from .impact_model import MarketImpactModel
from .models import (
    ExecutionAlgorithm,
    ExecutionOutcome,
    ExecutionPlan,
    ExecutionQuality,
    ExecutionSlice,
    ExecutionTask,
    ImpactEstimate,
    MarketState,
    OrderSide,
    OrderUrgency,
    PlanStatus,
    SliceStatus,
)
from .optimizer import ExecutionOptimizer
from .slicer import OrderSlicer

__all__ = [
    # Models
    "ExecutionAlgorithm",
    "ExecutionOutcome",
    "ExecutionPlan",
    "ExecutionQuality",
    "ExecutionSlice",
    "ExecutionTask",
    "ImpactEstimate",
    "MarketState",
    "OrderSide",
    "OrderUrgency",
    "PlanStatus",
    "SliceStatus",
    # Slicer
    "OrderSlicer",
    # Algorithms
    "TwapExecutor",
    "VwapExecutor",
    "PovExecutor",
    "AdaptiveExecutor",
    # Impact
    "MarketImpactModel",
    # Optimizer
    "ExecutionOptimizer",
]
