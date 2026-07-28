"""Performance Attribution – decompose portfolio returns into sources."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AttributionResult:
    """Performance attribution breakdown.

    Decomposes total return into:
    - Stock Selection (alpha from individual picks)
    - Factor Exposure (style factor contributions)
    - Market Beta (systematic market return)
    - Sector Allocation (sector weight decisions)
    - Interaction / Residual
    """

    period: str = ""  # e.g. "Q1 2026"
    total_return: float = 0.0
    stock_selection: float = 0.0
    factor_exposure: float = 0.0
    market_beta: float = 0.0
    sector_allocation: float = 0.0
    residual: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "period": self.period,
            "total_return": self.total_return,
            "stock_selection": self.stock_selection,
            "factor_exposure": self.factor_exposure,
            "market_beta": self.market_beta,
            "sector_allocation": self.sector_allocation,
            "residual": self.residual,
            "details": self.details,
        }


class PerformanceAttribution:
    """Analyzes portfolio returns and attributes them to specific sources.

    Supports Brinson-style attribution (allocation + selection) and
    factor-based decomposition for quant portfolios.
    """

    def __init__(self):
        pass

    def analyze(
        self,
        total_return: float,
        market_return: float = 0.0,
        stock_contributions: Optional[Dict[str, float]] = None,
        factor_contributions: Optional[Dict[str, float]] = None,
        sector_contributions: Optional[Dict[str, float]] = None,
        period: str = "",
    ) -> AttributionResult:
        """Perform full performance attribution.

        Args:
            total_return: Portfolio total return.
            market_return: Benchmark/market return (used as beta base).
            stock_contributions: Per-stock contribution to return.
            factor_contributions: Per-factor contribution.
            sector_contributions: Per-sector contribution.
            period: Label for the analysis period.
        """
        stock_selection = sum(stock_contributions.values()) if stock_contributions else 0.0
        factor_exposure = sum(factor_contributions.values()) if factor_contributions else 0.0
        sector_allocation = sum(sector_contributions.values()) if sector_contributions else 0.0

        explained = market_return + stock_selection + factor_exposure + sector_allocation
        residual = total_return - explained

        return AttributionResult(
            period=period,
            total_return=round(total_return, 4),
            market_beta=round(market_return, 4),
            stock_selection=round(stock_selection, 4),
            factor_exposure=round(factor_exposure, 4),
            sector_allocation=round(sector_allocation, 4),
            residual=round(residual, 4),
            details={
                "stock_contributions": stock_contributions or {},
                "factor_contributions": factor_contributions or {},
                "sector_contributions": sector_contributions or {},
            },
        )

    def analyze_simple(self, returns: float) -> dict:
        """Simple attribution for backward compatibility."""
        return {
            "total_return": returns,
            "market_beta": returns * 0.3,
            "stock_selection": returns * 0.4,
            "factor_exposure": returns * 0.2,
            "residual": returns * 0.1,
        }

    def contribution_summary(
        self, result: AttributionResult
    ) -> Dict[str, float]:
        """Extract contribution percentages for charting."""
        total_abs = (
            abs(result.market_beta)
            + abs(result.stock_selection)
            + abs(result.factor_exposure)
            + abs(result.sector_allocation)
            + abs(result.residual)
        )
        if total_abs == 0:
            return {}

        return {
            "Market Beta": result.market_beta / total_abs * 100,
            "Stock Selection": result.stock_selection / total_abs * 100,
            "Factor Exposure": result.factor_exposure / total_abs * 100,
            "Sector Allocation": result.sector_allocation / total_abs * 100,
            "Residual": result.residual / total_abs * 100,
        }

    def compare(
        self,
        current: AttributionResult,
        previous: AttributionResult,
    ) -> Dict[str, Any]:
        """Compare two attribution periods."""
        return {
            "current_period": current.period,
            "previous_period": previous.period,
            "return_change": current.total_return - previous.total_return,
            "stock_selection_change": current.stock_selection - previous.stock_selection,
            "factor_exposure_change": current.factor_exposure - previous.factor_exposure,
            "market_beta_change": current.market_beta - previous.market_beta,
        }
