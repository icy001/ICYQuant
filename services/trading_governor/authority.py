"""Risk Authority Controller – dynamically adjusts trading limits based on real-time risk."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


@dataclass
class RiskLimits:
    max_position: float = 0.0
    daily_loss_limit: float = 0.0
    exposure_limit: float = 0.0
    leverage_limit: int = 5
    margin_requirement: float = 0.2
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class RiskAuthorityController:
    """Dynamically controls position limits, loss limits, exposure, leverage, and margin.

    Adjusts limits based on real-time risk score and market conditions.
    """

    def __init__(self) -> None:
        self._limits = RiskLimits()
        self._adjustment_history: list = []

    def leverage_limit(self, risk_score: float) -> int:
        """Determine maximum leverage based on risk score (0-1, higher = riskier).

        Args:
            risk_score: risk score in [0, 1].

        Returns:
            Maximum allowed leverage multiplier.
        """
        if risk_score > 0.8:
            return 1
        if risk_score > 0.5:
            return 2
        return 5

    def position_limit(self, risk_score: float, base_limit: float) -> float:
        """Scale position limit inversely with risk score."""
        if risk_score >= 0.8:
            return base_limit * 0.25
        if risk_score >= 0.5:
            return base_limit * 0.50
        if risk_score >= 0.3:
            return base_limit * 0.75
        return base_limit

    def exposure_limit(self, risk_score: float, base_exposure: float) -> float:
        """Scale exposure limit inversely with risk score."""
        return self.position_limit(risk_score, base_exposure)

    def daily_loss_limit(self, risk_score: float, base_loss: float) -> float:
        """Tighten daily loss limit as risk increases."""
        if risk_score >= 0.8:
            return base_loss * 0.3
        if risk_score >= 0.5:
            return base_loss * 0.6
        return base_loss

    def adjust_all(
        self,
        risk_score: float,
        base_position: float = 0.0,
        base_exposure: float = 0.0,
        base_loss: float = 0.0,
    ) -> RiskLimits:
        """Adjust all limits at once based on current risk score.

        Args:
            risk_score: current risk score (0-1).
            base_position: base max position.
            base_exposure: base exposure limit.
            base_loss: base daily loss limit.

        Returns:
            Updated RiskLimits.
        """
        self._limits = RiskLimits(
            max_position=self.position_limit(risk_score, base_position),
            daily_loss_limit=self.daily_loss_limit(risk_score, base_loss),
            exposure_limit=self.exposure_limit(risk_score, base_exposure),
            leverage_limit=self.leverage_limit(risk_score),
            margin_requirement=0.2 if risk_score < 0.5 else 0.3 if risk_score < 0.8 else 0.5,
        )
        self._adjustment_history.append({"risk_score": risk_score, "limits": self._limits})
        return self._limits

    @property
    def current_limits(self) -> RiskLimits:
        return self._limits

    @property
    def adjustment_count(self) -> int:
        return len(self._adjustment_history)
