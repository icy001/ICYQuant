from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ExposureLevel(str, Enum):
    AGGRESSIVE = "AGGRESSIVE"
    MODERATE = "MODERATE"
    CONSERVATIVE = "CONSERVATIVE"
    DEFENSIVE = "DEFENSIVE"
    LIQUIDATION = "LIQUIDATION"


class ExposureDirection(str, Enum):
    INCREASE = "INCREASE"
    DECREASE = "DECREASE"
    MAINTAIN = "MAINTAIN"


@dataclass
class ExposureState:
    current_exposure: float  # 0-1
    target_exposure: float
    net_exposure: float
    gross_exposure: float
    level: ExposureLevel
    market_beta: float = 1.0
    sector_exposure: Dict[str, float] = field(default_factory=dict)


@dataclass
class ExposureAdjustment:
    symbol: str
    current: float
    target: float
    delta: float
    direction: ExposureDirection
    reason: str
    triggers: List[str] = field(default_factory=list)


class DynamicExposureControl:
    """Dynamic Exposure Control Engine - adjusts portfolio exposure based on market conditions."""

    def __init__(self):
        self.states: List[ExposureState] = []
        self.adjustments: List[ExposureAdjustment] = []

    def adjust(self, exposure):
        """Adjust portfolio exposure dynamically.

        Args:
            exposure: Exposure data (str, float, dict, or ExposureState).

        Returns:
            Dict containing adjusted exposure.
        """
        if isinstance(exposure, ExposureState):
            return self._process_state(exposure)
        if isinstance(exposure, dict):
            return self._adjust_dict(exposure)
        if isinstance(exposure, (int, float)):
            return {"exposure": exposure}
        return {"exposure": exposure}

    def _process_state(self, state: ExposureState) -> dict:
        self.states.append(state)
        return self._state_to_dict(state)

    def _adjust_dict(self, data: dict) -> dict:
        current_exposure = data.get("current_exposure", 0.5)
        market_regime = data.get("market_regime", "NORMAL")
        volatility = data.get("volatility", 0.15)
        risk_level = data.get("risk_level", "MEDIUM")
        conviction = data.get("conviction", 50)
        liquidity = data.get("liquidity", "NORMAL")

        # Calculate target exposure
        target = self._calc_target_exposure(
            current_exposure, market_regime, volatility, risk_level, conviction, liquidity
        )

        # Determine exposure level
        level = self._determine_level(target)

        # Calculate net and gross
        long_pct = data.get("long_exposure", current_exposure)
        short_pct = data.get("short_exposure", 0.0)
        net = long_pct - short_pct
        gross = long_pct + short_pct

        state = ExposureState(
            current_exposure=round(current_exposure, 4),
            target_exposure=round(target, 4),
            net_exposure=round(net, 4),
            gross_exposure=round(gross, 4),
            level=level,
            market_beta=data.get("market_beta", 1.0),
            sector_exposure=data.get("sector_exposure", {}),
        )
        self.states.append(state)

        # Generate adjustment if delta is significant
        adjustment = None
        delta = target - current_exposure
        if abs(delta) > 0.02:
            direction = ExposureDirection.INCREASE if delta > 0 else ExposureDirection.DECREASE
            adjustment = ExposureAdjustment(
                symbol="PORTFOLIO",
                current=round(current_exposure, 4),
                target=round(target, 4),
                delta=round(delta, 4),
                direction=direction,
                reason=self._adjustment_reason(direction, market_regime, volatility),
                triggers=self._identify_triggers(market_regime, volatility, risk_level),
            )
            self.adjustments.append(adjustment)

        result = self._state_to_dict(state)
        if adjustment:
            result["exposure"]["adjustment"] = {
                "direction": adjustment.direction.value,
                "delta": adjustment.delta,
                "reason": adjustment.reason,
                "triggers": adjustment.triggers,
            }
        return result

    def _calc_target_exposure(
        self, current: float, regime: str, vol: float, risk: str,
        conviction: float, liquidity: str
    ) -> float:
        base = current

        # Regime adjustments
        regime_factors = {
            "BULL": 1.15, "BULLISH": 1.10, "NORMAL": 1.0,
            "BEARISH": 0.85, "BEAR": 0.70, "CRISIS": 0.40,
            "HIGH_VOL": 0.75, "SIDEWAYS": 0.95,
        }
        base *= regime_factors.get(regime.upper(), 1.0)

        # Volatility adjustment
        if vol > 0.35:
            base *= 0.6
        elif vol > 0.25:
            base *= 0.8
        elif vol > 0.15:
            base *= 0.95

        # Risk level adjustment
        risk_factors = {"LOW": 1.1, "MEDIUM": 1.0, "HIGH": 0.75, "CRITICAL": 0.40}
        base *= risk_factors.get(risk.upper(), 1.0)

        # Conviction boost
        if conviction >= 80:
            base *= 1.10
        elif conviction >= 60:
            base *= 1.05
        elif conviction < 40:
            base *= 0.90

        # Liquidity adjustment
        if liquidity.upper() == "LOW":
            base *= 0.85
        elif liquidity.upper() == "ILLIQUID":
            base *= 0.60

        return max(0.0, min(1.0, base))

    def _determine_level(self, exposure: float) -> ExposureLevel:
        if exposure >= 0.80:
            return ExposureLevel.AGGRESSIVE
        if exposure >= 0.60:
            return ExposureLevel.MODERATE
        if exposure >= 0.30:
            return ExposureLevel.CONSERVATIVE
        if exposure > 0.05:
            return ExposureLevel.DEFENSIVE
        return ExposureLevel.LIQUIDATION

    def _adjustment_reason(self, direction: ExposureDirection, regime: str, vol: float) -> str:
        if direction == ExposureDirection.INCREASE:
            return f"Increasing exposure: favorable regime ({regime}), manageable volatility ({vol:.0%})"
        return f"Reducing exposure: {regime} regime, elevated volatility ({vol:.0%})"

    def _identify_triggers(self, regime: str, vol: float, risk: str) -> List[str]:
        triggers = []
        if regime.upper() in ("CRISIS", "BEAR"):
            triggers.append("Crisis circuit breaker activated")
        if vol > 0.30:
            triggers.append(f"Volatility circuit breaker (vol={vol:.0%})")
        if risk.upper() in ("HIGH", "CRITICAL"):
            triggers.append("Risk limit breached")
        return triggers if triggers else ["Normal exposure adjustment"]

    def _state_to_dict(self, state: ExposureState) -> dict:
        return {
            "exposure": {
                "current_exposure": state.current_exposure,
                "target_exposure": state.target_exposure,
                "net_exposure": state.net_exposure,
                "gross_exposure": state.gross_exposure,
                "level": state.level.value,
                "market_beta": state.market_beta,
                "sector_exposure": state.sector_exposure,
            }
        }

    def get_state(self) -> Optional[ExposureState]:
        """Get the latest exposure state."""
        return self.states[-1] if self.states else None

    def get_adjustments(self) -> List[ExposureAdjustment]:
        """Get all exposure adjustments."""
        return list(self.adjustments)
