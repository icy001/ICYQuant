"""AI Capital Flow Intelligence Engine.

Tracks global capital movement, identifies institutional money, smart money,
ETF flows, and cross-asset migration. Converts flow behavior into tradeable
signals for capital-driven alpha generation.
"""

from __future__ import annotations

from .record import (
    CapitalFlowRecord,
    FlowSource,
    FlowDirection,
    FlowAssetClass,
    FlowEvent,
    SectorRotation,
    FlowAlphaSignal,
    InstitutionalBehavior,
    SmartMoneyAction,
    LiquidityRegime,
)
from .collector import CapitalFlowCollector, FlowCollectionResult
from .institutional import InstitutionalFlowDetector, InstitutionalFlowResult
from .smart_money import SmartMoneyTracker, SmartMoneyResult
from .etf_flow import ETFFlowAnalyzer, ETFFlowResult
from .options_flow import OptionsFlowAnalyzer, OptionsFlowResult
from .liquidity import LiquidityPredictor, LiquidityResult
from .rotation import CapitalRotationEngine, RotationResult
from .alpha import FlowAlphaGenerator, FlowAlphaResult
from .memory import CapitalMemory, CapitalMemoryEntry
from .service import CapitalFlowIntelligenceService, FlowPipelineResult

__all__ = [
    # Data Models
    "CapitalFlowRecord",
    "FlowSource",
    "FlowDirection",
    "FlowAssetClass",
    "FlowEvent",
    "SectorRotation",
    "FlowAlphaSignal",
    "InstitutionalBehavior",
    "SmartMoneyAction",
    "LiquidityRegime",
    # Collector
    "CapitalFlowCollector",
    "FlowCollectionResult",
    # Institutional
    "InstitutionalFlowDetector",
    "InstitutionalFlowResult",
    # Smart Money
    "SmartMoneyTracker",
    "SmartMoneyResult",
    # ETF
    "ETFFlowAnalyzer",
    "ETFFlowResult",
    # Options
    "OptionsFlowAnalyzer",
    "OptionsFlowResult",
    # Liquidity
    "LiquidityPredictor",
    "LiquidityResult",
    # Rotation
    "CapitalRotationEngine",
    "RotationResult",
    # Alpha
    "FlowAlphaGenerator",
    "FlowAlphaResult",
    # Memory
    "CapitalMemory",
    "CapitalMemoryEntry",
    # Service
    "CapitalFlowIntelligenceService",
    "FlowPipelineResult",
]
