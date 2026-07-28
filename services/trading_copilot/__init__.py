"""AI Trading Copilot – quant trading assistant layer.

Provides:
- Market Analysis Assistant
- Position Analysis Assistant
- Risk Warning Engine
- Trade Planning Assistant
- Trade Review Assistant
- Trading Memory
- Copilot Engine
- Copilot Service
"""

from .market_analysis import MarketAnalysis, MarketAnalyst
from .position import PositionAnalysis, PositionAssistant
from .risk_alert import RiskAlert, RiskMonitor
from .trade_plan import TradePlan, TradePlanner
from .review import TradeReview, TradeReviewer
from .memory import TradingMemory, MemoryRecord
from .copilot import TradingCopilot
from .service import TradingCopilotService

__all__ = [
    "MarketAnalysis",
    "MarketAnalyst",
    "PositionAnalysis",
    "PositionAssistant",
    "RiskAlert",
    "RiskMonitor",
    "TradePlan",
    "TradePlanner",
    "TradeReview",
    "TradeReviewer",
    "TradingMemory",
    "MemoryRecord",
    "TradingCopilot",
    "TradingCopilotService",
]
