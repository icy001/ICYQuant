"""Position Analysis Assistant – explain current holdings."""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class PositionAnalysis:
    """Describes a single position's exposure, strengths, risks, and commentary."""

    symbol: str
    exposure: float  # 0.0 – 1.0 weight in portfolio
    strengths: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    comment: str = ""

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "exposure": self.exposure,
            "strengths": self.strengths,
            "risks": self.risks,
            "comment": self.comment,
        }


class PositionAssistant:
    """Analyses portfolio positions and generates human-readable explanations.

    Considers momentum, valuation, concentration risk, and volatility to
    produce actionable position commentary for traders.
    """

    def analyze_position(
        self,
        symbol: str,
        exposure: float,
        momentum: float = 0.0,
        valuation_high: bool = False,
        sector_concentration: float = 0.0,
        volatility: float = 0.0,
    ) -> PositionAnalysis:
        """Analyse a single position and return structured commentary."""
        strengths: List[str] = []
        risks: List[str] = []

        # Momentum
        if momentum > 0.3:
            strengths.append("Momentum Strong")
        elif momentum < -0.3:
            risks.append("Momentum Weak")

        # Valuation
        if valuation_high:
            risks.append("Valuation High")
        else:
            strengths.append("Valuation Reasonable")

        # Concentration
        if sector_concentration > 0.4:
            risks.append("Sector Concentration")

        # Volatility
        if volatility > 0.6:
            risks.append("High Volatility")

        # Build comment
        parts: List[str] = [f"{symbol}: Exposure {exposure:.1%}."]
        if strengths:
            parts.append(f"Strengths: {'; '.join(strengths)}.")
        if risks:
            parts.append(f"Risks: {'; '.join(risks)}.")
        comment = " ".join(parts)

        return PositionAnalysis(
            symbol=symbol,
            exposure=exposure,
            strengths=strengths,
            risks=risks,
            comment=comment,
        )

    def portfolio_overview(
        self, positions: List[PositionAnalysis]
    ) -> dict:
        """Generate a portfolio-level summary from individual position analyses."""
        total_exposure = sum(p.exposure for p in positions)
        all_risks: List[str] = []
        for p in positions:
            all_risks.extend(p.risks)

        concentration_warning = None
        if total_exposure > 0.9:
            concentration_warning = "Portfolio nearly fully invested; limited dry powder."

        return {
            "total_exposure": total_exposure,
            "position_count": len(positions),
            "top_risks": list(set(all_risks))[:5],
            "concentration_warning": concentration_warning,
            "positions": [p.to_dict() for p in positions],
        }
