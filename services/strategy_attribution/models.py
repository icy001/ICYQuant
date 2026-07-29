"""Strategy Performance Attribution Models - core data structures for attribution analysis."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class AttributionSource(str, Enum):
    """Source of return contribution."""
    ALPHA = "ALPHA"
    MARKET_BETA = "MARKET_BETA"
    STYLE_FACTOR = "STYLE_FACTOR"
    SECTOR_EXPOSURE = "SECTOR_EXPOSURE"
    POSITION_SIZING = "POSITION_SIZING"
    EXECUTION_QUALITY = "EXECUTION_QUALITY"
    RISK_CONTROL = "RISK_CONTROL"
    CURRENCY = "CURRENCY"
    RESIDUAL = "RESIDUAL"


class AttributionPeriod(str, Enum):
    """Attribution analysis period."""
    INTRADAY = "INTRADAY"
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    ANNUAL = "ANNUAL"
    CUSTOM = "CUSTOM"


class AttributionStatus(str, Enum):
    """Status of an attribution analysis."""
    PENDING = "PENDING"
    CALCULATING = "CALCULATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REVIEWED = "REVIEWED"


class FactorCategory(str, Enum):
    """Style factor categories for factor attribution."""
    MOMENTUM = "MOMENTUM"
    VALUE = "VALUE"
    QUALITY = "QUALITY"
    GROWTH = "GROWTH"
    VOLATILITY = "VOLATILITY"
    SIZE = "SIZE"
    LIQUIDITY = "LIQUIDITY"
    LEVERAGE = "LEVERAGE"
    DIVIDEND_YIELD = "DIVIDEND_YIELD"
    CUSTOM = "CUSTOM"


class TradeQuality(str, Enum):
    """Trade execution quality grading."""
    EXCELLENT = "EXCELLENT"
    GOOD = "GOOD"
    AVERAGE = "AVERAGE"
    POOR = "POOR"
    FAILED = "FAILED"


@dataclass
class ReturnComponent:
    """Single return attribution component."""

    source: AttributionSource
    contribution_bps: float
    weight_pct: float
    return_contribution_pct: float
    explanation: str
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FactorExposure:
    """Factor exposure contribution."""

    category: FactorCategory
    exposure: float
    return_contribution_bps: float
    factor_return: float
    t_stat: float = 0.0
    significance: str = ""


@dataclass
class SectorContribution:
    """Sector/industry exposure contribution."""

    sector: str
    allocation_weight: float
    benchmark_weight: float
    active_weight: float
    sector_return: float
    contribution_bps: float


@dataclass
class TradeAttribution:
    """Trade execution attribution."""

    trade_id: str
    symbol: str
    side: str
    quantity: float
    arrival_price: float
    execution_price: float
    slippage_bps: float
    market_impact_bps: float
    commission_bps: float
    total_cost_bps: float
    quality: TradeQuality


@dataclass
class PositionContribution:
    """Position sizing contribution."""

    symbol: str
    weight: float
    return_pct: float
    contribution_bps: float
    is_overweight: bool
    risk_budget_used: float


@dataclass
class PerformanceAttribution:
    """Complete performance attribution for a strategy.

    Decomposes total return into component sources:
    Total PnL = Alpha + Market Beta + Factor Exposure + Sector Exposure
              + Position Sizing + Execution Quality - Risk Penalty + Residual
    """

    strategy_id: str
    period: str
    period_type: AttributionPeriod

    # Aggregate returns
    total_return_bps: float
    total_return_pct: float

    # Attribution components
    alpha_return_bps: float
    beta_return_bps: float
    factor_return_bps: float
    sector_return_bps: float
    position_sizing_bps: float
    execution_return_bps: float
    risk_adjustment_bps: float
    residual_bps: float

    # Detailed breakdowns
    components: List[ReturnComponent] = field(default_factory=list)
    factor_exposures: List[FactorExposure] = field(default_factory=list)
    sector_contributions: List[SectorContribution] = field(default_factory=list)
    trade_attributions: List[TradeAttribution] = field(default_factory=list)
    position_contributions: List[PositionContribution] = field(default_factory=list)

    # Meta
    status: AttributionStatus = AttributionStatus.PENDING
    confidence_score: float = 0.0
    attribution_id: str = ""
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "attribution_id": self.attribution_id,
            "strategy_id": self.strategy_id,
            "period": self.period,
            "period_type": self.period_type.value,
            "total_return_bps": self.total_return_bps,
            "total_return_pct": self.total_return_pct,
            "alpha_return_bps": self.alpha_return_bps,
            "beta_return_bps": self.beta_return_bps,
            "factor_return_bps": self.factor_return_bps,
            "sector_return_bps": self.sector_return_bps,
            "position_sizing_bps": self.position_sizing_bps,
            "execution_return_bps": self.execution_return_bps,
            "risk_adjustment_bps": self.risk_adjustment_bps,
            "residual_bps": self.residual_bps,
            "components": [
                {
                    "source": c.source.value,
                    "contribution_bps": c.contribution_bps,
                    "weight_pct": c.weight_pct,
                    "return_contribution_pct": c.return_contribution_pct,
                    "explanation": c.explanation,
                    "confidence": c.confidence,
                }
                for c in self.components
            ],
            "factor_exposures": [
                {
                    "category": f.category.value,
                    "exposure": f.exposure,
                    "return_contribution_bps": f.return_contribution_bps,
                    "factor_return": f.factor_return,
                    "t_stat": f.t_stat,
                    "significance": f.significance,
                }
                for f in self.factor_exposures
            ],
            "sector_contributions": [
                {
                    "sector": s.sector,
                    "allocation_weight": s.allocation_weight,
                    "benchmark_weight": s.benchmark_weight,
                    "active_weight": s.active_weight,
                    "sector_return": s.sector_return,
                    "contribution_bps": s.contribution_bps,
                }
                for s in self.sector_contributions
            ],
            "trade_attributions_count": len(self.trade_attributions),
            "position_contributions_count": len(self.position_contributions),
            "status": self.status.value,
            "confidence_score": self.confidence_score,
            "notes": self.notes,
        }


@dataclass
class MultiStrategyAttribution:
    """Multi-strategy portfolio attribution."""

    portfolio_id: str
    period: str
    total_return_bps: float

    # Per-strategy breakdown
    strategy_attributions: List[PerformanceAttribution] = field(default_factory=list)

    # Cross-strategy analysis
    correlation_matrix: Dict[str, Dict[str, float]] = field(default_factory=dict)
    diversification_benefit_bps: float = 0.0
    top_contributors: List[Dict[str, Any]] = field(default_factory=list)
    bottom_contributors: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "portfolio_id": self.portfolio_id,
            "period": self.period,
            "total_return_bps": self.total_return_bps,
            "strategy_attributions": [s.to_dict() for s in self.strategy_attributions],
            "correlation_matrix": self.correlation_matrix,
            "diversification_benefit_bps": self.diversification_benefit_bps,
            "top_contributors": self.top_contributors,
            "bottom_contributors": self.bottom_contributors,
        }


@dataclass
class AttributionSummary:
    """Human-readable attribution summary."""

    strategy_id: str
    period: str
    headline: str
    key_drivers: List[str]
    key_detractors: List[str]
    recommendation: str
    alpha_quality: str  # "STRONG", "MODERATE", "WEAK", "NEGATIVE"
    risk_efficiency: str  # "EFFICIENT", "ADEQUATE", "INEFFICIENT"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "period": self.period,
            "headline": self.headline,
            "key_drivers": self.key_drivers,
            "key_detractors": self.key_detractors,
            "recommendation": self.recommendation,
            "alpha_quality": self.alpha_quality,
            "risk_efficiency": self.risk_efficiency,
        }
