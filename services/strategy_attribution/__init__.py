"""Strategy Performance Attribution Engine - decomposes strategy returns into component sources."""

from .models import (
    AttributionPeriod,
    AttributionSource,
    AttributionStatus,
    AttributionSummary,
    FactorCategory,
    FactorExposure,
    MultiStrategyAttribution,
    PerformanceAttribution,
    PositionContribution,
    ReturnComponent,
    SectorContribution,
    TradeAttribution,
    TradeQuality,
)
from .calculator import AttributionCalculator
from .analyzer import StrategyAnalyzer
from .service import StrategyAttributionService

__all__ = [
    # Engine classes
    "AttributionCalculator",
    "StrategyAnalyzer",
    "StrategyAttributionService",
    # Core dataclasses
    "PerformanceAttribution",
    "MultiStrategyAttribution",
    "AttributionSummary",
    "ReturnComponent",
    "FactorExposure",
    "SectorContribution",
    "TradeAttribution",
    "PositionContribution",
    # Enums
    "AttributionSource",
    "AttributionPeriod",
    "AttributionStatus",
    "FactorCategory",
    "TradeQuality",
]
