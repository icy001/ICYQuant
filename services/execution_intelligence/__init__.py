"""AI Execution Intelligence Engine – smart order execution layer.

Provides:
- Execution Order Model
- Execution Plan & Slicing
- Smart Order Routing
- Slippage Prediction
- Market Impact Analysis
- Execution Strategy Engine (VWAP, TWAP, POV, Adaptive)
- Transaction Cost Analysis
- Execution Intelligence Service
"""

from .order import ExecutionOrder, OrderSide, OrderType, OrderStatus
from .plan import ExecutionPlan, Slice
from .routing import SmartRoutingEngine, Venue
from .slippage import SlippagePredictor, SlippageEstimate
from .impact import MarketImpactModel, ImpactEstimate
from .strategy import ExecutionStrategyEngine, StrategyConfig
from .tca import TransactionCostAnalyzer, TCAResult
from .service import ExecutionIntelligenceService

__all__ = [
    "ExecutionOrder",
    "OrderSide",
    "OrderType",
    "OrderStatus",
    "ExecutionPlan",
    "Slice",
    "SmartRoutingEngine",
    "Venue",
    "SlippagePredictor",
    "SlippageEstimate",
    "MarketImpactModel",
    "ImpactEstimate",
    "ExecutionStrategyEngine",
    "StrategyConfig",
    "TransactionCostAnalyzer",
    "TCAResult",
    "ExecutionIntelligenceService",
]
