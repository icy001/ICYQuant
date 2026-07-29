"""Risk Attribution Engine - identifies which positions create the most risk."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class RiskMeasure(str, Enum):
    VOLATILITY = "VOLATILITY"
    VAR = "VAR"
    CVAR = "CVAR"
    MARGINAL_RISK = "MARGINAL_RISK"
    RISK_CONTRIBUTION = "RISK_CONTRIBUTION"
    CONCENTRATION = "CONCENTRATION"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class PositionRisk:
    symbol: str
    weight: float
    standalone_risk: float
    marginal_risk: float
    risk_contribution_pct: float
    var_95: float
    cvar_95: float
    risk_level: RiskLevel
    diversification_benefit: float


@dataclass
class RiskAttributionReport:
    report_id: str
    portfolio_risk: float
    position_risks: List[PositionRisk]
    concentration_ratio: float
    top_risk_contributors: List[str]
    diversification_score: float


class RiskAttributionEngine:
    """Risk Attribution Engine.

    Answers: Which positions create the most risk?
    Analyzes: Position-level risk, VaR, CVaR, marginal risk, concentration.
    """

    def __init__(self):
        self.reports: List[RiskAttributionReport] = []

    def analyze(self, positions) -> Dict[str, Any]:
        """Analyze risk attribution across positions.

        Args:
            positions: Position data to analyze.

        Returns:
            Dict with risk attribution analysis.
        """
        if isinstance(positions, dict):
            return self._analyze_from_dict(positions)
        return {"risk": positions}

    def _analyze_from_dict(self, positions: Dict[str, Any]) -> Dict[str, Any]:
        """Perform risk attribution from structured data."""
        pos_list = positions.get("positions", [])
        portfolio_vol = positions.get("portfolio_volatility", 0.15)
        total_nav = positions.get("total_nav", 1000000.0)

        if not pos_list:
            return {
                "risk": positions,
                "portfolio_risk": portfolio_vol,
                "position_risks": [],
                "message": "No positions to analyze",
            }

        position_risks = []
        total_weight = sum(p.get("weight", 0.0) for p in pos_list)

        for pos in pos_list:
            weight = pos.get("weight", 0.0) / total_weight if total_weight > 0 else 0.0
            symbol = pos.get("symbol", "UNKNOWN")

            standalone_risk = pos.get("volatility", portfolio_vol)
            marginal_risk = weight * standalone_risk

            var_95 = self._estimate_var(weight, total_nav, standalone_risk, 0.95)
            cvar_95 = self._estimate_cvar(weight, total_nav, standalone_risk, 0.95)

            risk_level = self._classify_risk(weight, standalone_risk)

            diversification_benefit = 1.0 - (marginal_risk / standalone_risk if standalone_risk > 0 else 0.0)
            diversification_benefit = max(0.0, min(1.0, diversification_benefit))

            position_risks.append(PositionRisk(
                symbol=symbol,
                weight=weight,
                standalone_risk=standalone_risk,
                marginal_risk=marginal_risk,
                risk_contribution_pct=0.0,
                var_95=var_95,
                cvar_95=cvar_95,
                risk_level=risk_level,
                diversification_benefit=diversification_benefit,
            ))

        # Compute risk contributions
        total_marginal = sum(pr.marginal_risk for pr in position_risks)
        for pr in position_risks:
            pr.risk_contribution_pct = (pr.marginal_risk / total_marginal * 100.0) if total_marginal > 0 else 0.0

        # Sort by risk contribution
        position_risks.sort(key=lambda x: x.risk_contribution_pct, reverse=True)

        # Concentration ratio (top 3 / total)
        top3_risk = sum(pr.risk_contribution_pct for pr in position_risks[:3])
        concentration_ratio = top3_risk / 100.0 if position_risks else 0.0

        # Diversification score
        n = len(position_risks)
        if n > 1:
            weights_sum_sq = sum(pr.weight ** 2 for pr in position_risks)
            diversification_score = 1.0 / (weights_sum_sq * n) if weights_sum_sq > 0 else 0.0
        else:
            diversification_score = 0.0

        top_contributors = [pr.symbol for pr in position_risks[:3]]

        report = RiskAttributionReport(
            report_id=f"RISK_{len(self.reports):04d}",
            portfolio_risk=portfolio_vol,
            position_risks=position_risks,
            concentration_ratio=concentration_ratio,
            top_risk_contributors=top_contributors,
            diversification_score=diversification_score,
        )
        self.reports.append(report)

        return {
            "risk": positions,
            "portfolio_risk": portfolio_vol,
            "position_risks": [
                {
                    "symbol": pr.symbol,
                    "weight": pr.weight,
                    "risk_contribution_pct": pr.risk_contribution_pct,
                    "var_95": pr.var_95,
                    "cvar_95": pr.cvar_95,
                    "risk_level": pr.risk_level.value,
                    "diversification_benefit": pr.diversification_benefit,
                }
                for pr in position_risks
            ],
            "concentration_ratio": concentration_ratio,
            "top_risk_contributors": top_contributors,
            "diversification_score": diversification_score,
            "risk_concentration_warning": concentration_ratio > 0.6,
        }

    def _estimate_var(self, weight: float, nav: float, vol: float, confidence: float) -> float:
        z_scores = {0.95: 1.645, 0.99: 2.326}
        z = z_scores.get(confidence, 1.645)
        return weight * nav * vol * z

    def _estimate_cvar(self, weight: float, nav: float, vol: float, confidence: float) -> float:
        var = self._estimate_var(weight, nav, vol, confidence)
        tail_multiplier = 1.4
        return var * tail_multiplier

    def _classify_risk(self, weight: float, volatility: float) -> RiskLevel:
        score = weight * volatility
        if score > 0.03:
            return RiskLevel.CRITICAL
        elif score > 0.02:
            return RiskLevel.HIGH
        elif score > 0.01:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    def get_latest_report(self) -> Optional[RiskAttributionReport]:
        """Get the most recent risk attribution report."""
        return self.reports[-1] if self.reports else None

    def get_high_risk_positions(self) -> List[PositionRisk]:
        """Get all positions with HIGH or CRITICAL risk level."""
        if not self.reports:
            return []
        latest = self.reports[-1]
        return [pr for pr in latest.position_risks
                if pr.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)]
