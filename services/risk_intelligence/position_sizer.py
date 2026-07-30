from dataclasses import dataclass
from typing import Optional

from .risk_predictor import RiskPrediction
from .market_regime import MarketRegime
from .black_swan import BlackSwanEvent


@dataclass
class PositionSize:
    theoretical_pct: float
    adjusted_pct: float
    risk_factor: float
    signal_factor: float
    liquidity_factor: float


class DynamicPositionSizer:
    def size(
        self,
        signal_confidence: float = 0.8,
        risk_prediction: Optional[RiskPrediction] = None,
        market_regime: Optional[MarketRegime] = None,
        black_swan: Optional[BlackSwanEvent] = None,
        liquidity_score: float = 0.8,
        max_portfolio_pct: float = 0.10,
    ) -> PositionSize:
        signal_factor = min(signal_confidence, 1.0)

        if risk_prediction:
            risk_factor = 1.0 - (risk_prediction.risk_score / 200.0)
        else:
            risk_factor = 0.5

        if market_regime:
            regime_factor = market_regime.max_position_pct / 0.10
        else:
            regime_factor = 1.0

        if black_swan and black_swan.detected:
            if black_swan.level == "EXTREME":
                bs_factor = 0.0
            elif black_swan.level == "CRITICAL":
                bs_factor = 0.2
            else:
                bs_factor = 0.5
        else:
            bs_factor = 1.0

        liquidity_factor = min(liquidity_score, 1.0)

        theoretical = max_portfolio_pct * signal_factor * regime_factor
        adjusted = theoretical * risk_factor * bs_factor * liquidity_factor

        return PositionSize(
            theoretical_pct=round(theoretical, 4),
            adjusted_pct=round(max(adjusted, 0.0), 4),
            risk_factor=round(risk_factor, 4),
            signal_factor=round(signal_factor, 4),
            liquidity_factor=round(liquidity_factor, 4),
        )
