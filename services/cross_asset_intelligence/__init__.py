"""AI Cross Asset Intelligence Engine.

Establishes dynamic relationship models between global assets, understands
capital transmission paths across equities, bonds, currencies, commodities,
gold, and crypto, and converts cross-asset changes into trading signals,
risk signals, and asset allocation recommendations.
"""

from __future__ import annotations

from .relationship import (
    AssetRelationship,
    AssetClass,
    RelationshipType,
    RiskRegime,
    DollarTrend,
    AssetNode,
    RelationshipGraph,
    CrossAssetSignal,
)
from .equity_bond import EquityBondAnalyzer, EquityBondResult
from .dollar import DollarIntelligenceEngine, DollarResult
from .commodity import CommodityIntelligenceEngine, CommodityResult
from .crypto import (
    CryptoIntelligenceEngine,
    CryptoResult,
    CryptoDominance,
    CryptoRiskAppetite,
)
from .correlation import (
    CorrelationEngine,
    CorrelationResult,
    CorrelationMethod,
    CorrelationRegime,
)
from .rotation import (
    AssetRotationDetector,
    AssetRotationResult,
    RotationEvent,
    RotationType,
    RotationRegime,
)
from .signal import (
    CrossAssetSignalGenerator,
    SignalResult,
    SignalPriority,
    SignalAction,
)
from .risk import (
    CrossAssetRiskMonitor,
    RiskMonitorResult,
    RiskLevel,
    RiskCategory,
    RiskComponent,
)
from .memory import CrossAssetMemory, CrossAssetMemoryEntry
from .service import CrossAssetIntelligenceService, CrossAssetPipelineResult

__all__ = [
    # Relationship Model
    "AssetRelationship",
    "AssetClass",
    "RelationshipType",
    "RiskRegime",
    "DollarTrend",
    "AssetNode",
    "RelationshipGraph",
    "CrossAssetSignal",
    # Equity-Bond
    "EquityBondAnalyzer",
    "EquityBondResult",
    # Dollar
    "DollarIntelligenceEngine",
    "DollarResult",
    # Commodity
    "CommodityIntelligenceEngine",
    "CommodityResult",
    # Crypto
    "CryptoIntelligenceEngine",
    "CryptoResult",
    "CryptoDominance",
    "CryptoRiskAppetite",
    # Correlation
    "CorrelationEngine",
    "CorrelationResult",
    "CorrelationMethod",
    "CorrelationRegime",
    # Rotation
    "AssetRotationDetector",
    "AssetRotationResult",
    "RotationEvent",
    "RotationType",
    "RotationRegime",
    # Signal
    "CrossAssetSignalGenerator",
    "SignalResult",
    "SignalPriority",
    "SignalAction",
    # Risk
    "CrossAssetRiskMonitor",
    "RiskMonitorResult",
    "RiskLevel",
    "RiskCategory",
    "RiskComponent",
    # Memory
    "CrossAssetMemory",
    "CrossAssetMemoryEntry",
    # Service
    "CrossAssetIntelligenceService",
    "CrossAssetPipelineResult",
]
