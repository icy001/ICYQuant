from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class RiskMetrics:
    var_95: float
    cvar_95: float
    beta: float
    sharpe_ratio: float
    max_drawdown: float


@dataclass
class SectorExposure:
    sector: str
    exposure_pct: float
    limit_pct: float
    over_limit: bool


@dataclass
class PortfolioRisk:
    total_exposure: float
    risk_metrics: RiskMetrics
    sector_exposures: List[SectorExposure]
    factor_exposures: Dict[str, float]


class PortfolioRiskEngine:
    def __init__(self):
        self.sector_limits = {
            "technology": 0.40,
            "financial": 0.30,
            "healthcare": 0.25,
            "consumer": 0.20,
            "energy": 0.20,
            "cash": 1.00,
        }

    def calculate_var(self, returns: List[float], confidence: float = 0.95) -> float:
        if not returns:
            return 0.0
        sorted_returns = sorted(returns)
        index = int(len(sorted_returns) * (1 - confidence))
        return abs(sorted_returns[max(0, index)])

    def calculate_cvar(self, returns: List[float], confidence: float = 0.95) -> float:
        if not returns:
            return 0.0
        var = self.calculate_var(returns, confidence)
        tail_returns = [r for r in returns if r <= -var]
        if not tail_returns:
            return var
        return abs(sum(tail_returns) / len(tail_returns))

    def calculate_beta(self, asset_returns: List[float], market_returns: List[float]) -> float:
        if len(asset_returns) != len(market_returns) or len(asset_returns) < 2:
            return 1.0
        mean_asset = sum(asset_returns) / len(asset_returns)
        mean_market = sum(market_returns) / len(market_returns)
        covariance = sum(
            (a - mean_asset) * (m - mean_market)
            for a, m in zip(asset_returns, market_returns)
        ) / len(asset_returns)
        variance = sum((m - mean_market) ** 2 for m in market_returns) / len(market_returns)
        if variance == 0:
            return 1.0
        return covariance / variance

    def assess_sector_exposure(
        self, sector: str, exposure_pct: float
    ) -> SectorExposure:
        limit = self.sector_limits.get(sector, 0.30)
        return SectorExposure(
            sector=sector,
            exposure_pct=exposure_pct,
            limit_pct=limit,
            over_limit=exposure_pct > limit,
        )

    def evaluate_portfolio(
        self,
        returns: List[float],
        sector_exposures: Dict[str, float],
        factor_exposures: Dict[str, float],
    ) -> PortfolioRisk:
        var_95 = self.calculate_var(returns)
        cvar_95 = self.calculate_cvar(returns)

        sector_list = [
            self.assess_sector_exposure(sector, exp)
            for sector, exp in sector_exposures.items()
        ]

        total_exp = sum(sector_exposures.values())

        metrics = RiskMetrics(
            var_95=round(var_95, 6),
            cvar_95=round(cvar_95, 6),
            beta=1.0,
            sharpe_ratio=0.0,
            max_drawdown=0.0,
        )

        return PortfolioRisk(
            total_exposure=round(total_exp, 4),
            risk_metrics=metrics,
            sector_exposures=sector_list,
            factor_exposures=factor_exposures,
        )
