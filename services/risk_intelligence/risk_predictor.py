from dataclasses import dataclass
from enum import Enum


class RiskLevel(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass
class RiskPrediction:
    risk_score: int
    risk_level: str
    recommendation: str
    volatility_score: float
    liquidity_score: float
    credit_score: float
    tail_score: float


class RiskPredictor:
    def predict(
        self,
        volatility: float = 0.2,
        liquidity: float = 0.8,
        credit_spread: float = 0.05,
        market_cap: float = 1.0,
        var_95: float = 0.02,
    ) -> RiskPrediction:
        vol_component = min(volatility * 100, 30)
        liq_component = (1 - liquidity) * 25
        cred_component = min(credit_spread * 500, 20)
        tail_component = min(var_95 * 500, 25)

        raw_score = vol_component + liq_component + cred_component + tail_component
        risk_score = min(int(raw_score), 100)

        if risk_score <= 30:
            risk_level = RiskLevel.LOW.value
            recommendation = "Maintain Current Exposure"
        elif risk_score <= 70:
            risk_level = RiskLevel.MEDIUM.value
            recommendation = "Monitor Positions"
        else:
            risk_level = RiskLevel.HIGH.value
            recommendation = "Reduce Exposure"

        return RiskPrediction(
            risk_score=risk_score,
            risk_level=risk_level,
            recommendation=recommendation,
            volatility_score=vol_component,
            liquidity_score=liq_component,
            credit_score=cred_component,
            tail_score=tail_component,
        )
