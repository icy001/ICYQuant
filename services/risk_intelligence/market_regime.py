from dataclasses import dataclass
from enum import Enum


class MarketRegimeType(Enum):
    BULL = "BULL"
    BEAR = "BEAR"
    SIDEWAY = "SIDEWAY"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    LOW_LIQUIDITY = "LOW_LIQUIDITY"
    RISK_OFF = "RISK_OFF"


@dataclass
class MarketRegime:
    regime_type: str
    confidence: float
    max_position_pct: float
    max_leverage: float


class MarketRegimeDetector:
    def detect(
        self,
        trend: float = 0.01,
        volatility: float = 0.15,
        volume_ratio: float = 1.0,
        spread: float = 0.0005,
    ) -> MarketRegime:
        if volatility > 0.35 and spread > 0.002:
            regime_type = MarketRegimeType.RISK_OFF.value
            confidence = 0.9
            max_position = 0.03
            max_leverage = 1.5
        elif volatility > 0.25:
            regime_type = MarketRegimeType.HIGH_VOLATILITY.value
            confidence = 0.85
            max_position = 0.05
            max_leverage = 2.0
        elif volume_ratio < 0.5 and spread > 0.001:
            regime_type = MarketRegimeType.LOW_LIQUIDITY.value
            confidence = 0.8
            max_position = 0.04
            max_leverage = 1.5
        elif trend > 0.02 and volatility < 0.15:
            regime_type = MarketRegimeType.BULL.value
            confidence = 0.9
            max_position = 0.10
            max_leverage = 3.0
        elif trend < -0.02 and volatility > 0.15:
            regime_type = MarketRegimeType.BEAR.value
            confidence = 0.85
            max_position = 0.03
            max_leverage = 1.5
        else:
            regime_type = MarketRegimeType.SIDEWAY.value
            confidence = 0.7
            max_position = 0.07
            max_leverage = 2.5

        return MarketRegime(
            regime_type=regime_type,
            confidence=confidence,
            max_position_pct=max_position,
            max_leverage=max_leverage,
        )
